import os
import re
from abc import abstractmethod
from collections.abc import Iterable
from typing import TypedDict, cast, overload

from . import env
from .cache import Cache
from .config import Config
from .execute import *
from .module import Module, Source
from .record import Record


def get_version(path: str) -> tuple[int, ...]:
    stdout, _ = background_execute(f'{path} --version | head -1')
    match = re.search(r' (?P<version>[0-9.]+)(-|\s|$)', stdout)
    if match is None:
        sys_exit(f'parse version of "{path}" failed')
    version = match.group('version')
    return tuple(map(int, version.split('.')))


@overload
def _pretty_join(iterable: Iterable[str]) -> str: ...

@overload
def _pretty_join(*args: str) -> str: ...


def _pretty_join(*args) -> str:    # type: ignore
    if isinstance(args[0], str):
        strings = args      # type: ignore
    else:
        strings = args[0]   # type: ignore
    cast(Iterable[str], strings)
    valid = [s for s in strings if s]   # type: ignore
    if valid:
        return ' '.join(valid)  # type: ignore
    return ''


VersionDetails = list[tuple[tuple[int, ...], str]]


class CompileCommand(TypedDict):
    directory: str
    command: str
    file: str


class Compiler:
    def __init__(self, path: str) -> None:
        self._path = path
        self._version = get_version(path)

    @property
    def path(self) -> str:
        return self._path

    @property
    def version(self) -> tuple[int, ...]:
        return self._version

    def _select_version(self, details: VersionDetails) -> str:
        return [detail for detail in details if detail[0] <= self.version][-1][1]

    @abstractmethod
    def max_cpp_std_version(self) -> str:
        ...

    @staticmethod
    def _options_str(source: Source, config: Config) -> str:
        options = config.options.copy()
        options.extend(sorted(source.options()))
        return _pretty_join(options)

    @staticmethod
    def _library_includes_str(source: Source) -> str:
        incls = (lib.include for lib in source.libraries() if lib.include is not None)
        return _pretty_join(f'-isystem {include}' for include in sorted(incls))

    @staticmethod
    def _library_paths_str(source: Source) -> str:
        paths = (lib.libpath for lib in source.libraries() if lib.libpath is not None)
        return _pretty_join(f'-L{path}' for path in sorted(paths))

    @staticmethod
    def _library_names(source: Source) -> list[str]:
        names : set[str] = set()
        for lib in source.libraries():
            if lib.libs is None:
                names.add(lib.name)
            else:
                names.update(lib.libs)
        return list(names)

    @staticmethod
    def _library_names_str(source: Source) -> str:
        return _pretty_join(f'-l{name}' for name in sorted(Compiler._library_names(source)))

    @staticmethod
    def _source_includes_str(source: Source) -> str:
        return _pretty_join(f'-I{incl}' for incl in sorted(source.includes))

    @staticmethod
    def _objects(source: Source) -> list[str]:
        return [dep.target for dep in source.sources()]

    @staticmethod
    def _objects_str(source: Source) -> str:
        return _pretty_join(sorted(Compiler._objects(source)))

    @staticmethod
    def _dependencies(source: Source) -> list[str]:
        dependencies = Compiler._objects(source)
        dependencies.extend(header.path for header in source.headers())
        dependencies.append(source.path)
        return dependencies

    def compile_record(self, source: Source, config: Config) -> Record:
        command = _pretty_join(
            self.path,
            f'-std={self.max_cpp_std_version()}',
            self._options_str(source, config),
            self._library_includes_str(source),
            self._source_includes_str(source),
            '-o',
            source.target,
            '-c',
            source.path,
        )
        return Record(source.target, command, self._dependencies(source))

    def _executable_compile_record(self, source: Source, config: Config) -> Record:
        exe = os.path.splitext(source.target)[0]
        command = _pretty_join(
            self.path,
            f'-std={self.max_cpp_std_version()}',
            self._options_str(source, config),
            self._library_paths_str(source),
            self._library_includes_str(source),
            self._source_includes_str(source),
            '-o',
            exe,
            self._objects_str(source),
            source.path,
            self._library_names_str(source),
        )
        return Record(exe, command, self._dependencies(source))

    def compile(self, source: Source, config: Config) -> str:
        cache = Cache()

        records = [self.compile_record(source, config) for source in source.sources()]

        procs : list[subprocess.Popen[bytes]] = []
        for record in records:
            if cache.has_cache(record):
                cprint(f'found cache for "{record.target}", skip compiling ...', Color.GREEN)
            else:
                os.makedirs(os.path.dirname(record.target), exist_ok=True)
                procs.append(foreground_execute_handle(record.command))

        wait_for_handles(procs)

        exe = self._executable_compile_record(source, config)

        if cache.has_cache(exe):
            cprint(f'found cache for "{exe.target}", skip compiling ...', Color.GREEN)
        else:
            os.makedirs(os.path.dirname(exe.target), exist_ok=True)
            foreground_execute(exe.command)

        records.append(exe)
        cache.save(records)

        os.chmod(exe.target, os.stat(exe.target).st_mode | 0o111)

        return exe.target

    def compile_commands(self, module: Module, config: Config) -> list[CompileCommand]:
        return [
            {
                'directory': os.path.join(env.root(), os.path.split(source.path)[0]),
                'command': self.compile_record(source, config).command,
                'file': source.path,
            }
            for source in module.sources
        ]


class GccCompiler(Compiler):
    VERSION_DETAILS : VersionDetails = [
        ((4, 7, 1), 'c++11'),
        ((4, 9), 'c++14'),
        ((5, 1), 'c++17'),
        ((10, 1), 'c++20'),
        ((11, 1), 'c++23'),
    ]

    def __init__(self, path: str) -> None:
        super().__init__(path)

    def __le__(self, other: 'Compiler') -> bool:
        return self.version < other.version

    # override
    def max_cpp_std_version(self) -> str:
        return self._select_version(self.VERSION_DETAILS)


class ClangCompiler(Compiler):
    VERSION_DETAILS : VersionDetails = [
        ((3, 3), 'c++11'),
        ((3, 4), 'c++14'),
        ((5,), 'c++17'),
        ((10,), 'c++20'),
        ((17, 0, 1), 'c++26'),
    ]

    def __init__(self, path: str) -> None:
        super().__init__(path)

    def __le__(self, other: 'Compiler') -> bool:
        return self.version < other.version

    # override
    def max_cpp_std_version(self) -> str:
        return self._select_version(self.VERSION_DETAILS)


def select_compiler(prefer: str) -> Compiler:
    gccs : list[GccCompiler] = []
    clangs : list[ClangCompiler] = []

    for path in os.environ['PATH'].split(':'):
        if not os.path.exists(path):
            continue
        for name in os.listdir(path):
            exe = os.path.join(path, name)
            try:
                if name.startswith('g++'):
                    gccs.append(GccCompiler(exe))
                elif name.startswith('clang++'):
                    clangs.append(ClangCompiler(exe))
            except Exception:
                cprint(f'import compiler "{exe}" failed', Color.RED)

    if len(gccs) + len(clangs) == 0:
        sys_exit('complier not found')

    if prefer == 'g++' or len(clangs) == 0:
        return max(gccs, key=lambda gcc: gcc.version)
    else:
        return max(clangs, key=lambda clang: clang.version)
