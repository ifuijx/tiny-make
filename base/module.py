import os
from collections.abc import Iterable
from queue import Queue
from typing import Optional, cast

from . import env
from .config import load_config
from .file import *
from .library import Library
from .utils import *


# root has a special name for clarity
MAIN_MODULE_NAME = 'MAIN'


def _module_name(module_path: str) -> str:
    if os.path.samefile(module_path, env.root()):
        return MAIN_MODULE_NAME
    return module_path


def _pretty_path_join(parent: str, *paths: str) -> str:
    if parent in ['.', env.root()]:
        return os.path.join(*paths)
    return os.path.join(parent, *paths)


class DependencyManager:
    def __init__(self) -> None:
        self._lib_mapping : dict[str, Library] = {}
        self._global_libs : list[Library] = []
        self._mod_mapping : dict[str, 'Module'] = {}

    @property
    def global_libraries(self) -> list[Library]:
        return self._global_libs

    @property
    def modules(self) -> Iterable['Module']:
        return self._mod_mapping.values()

    def register_library(self, library: Library, is_global: bool) -> Library:
        old = self._lib_mapping.get(library.name)
        if old is None:
            env.vprint(f'add library {library}')
            self._lib_mapping[library.name] = library
        elif old != library:
            sys_exit(f'duplicate library "{library.name}" with different contents')
        ret = self._lib_mapping[library.name]
        if is_global and not ret in self._global_libs:
            env.vprint(f'set library {library} global')
            self._global_libs.append(ret)
        return ret

    def register_module(self, module: 'Module') -> None:
        self._mod_mapping.setdefault(module.name, module)

    def link_module_path(self, parent: Optional['Module'], path: str) -> 'Module':
        link = env.add_link_path(path)
        name = _module_name(link)
        if parent is not None:
            env.vprint(f'{parent} link to "{name}"')
        if name not in self._mod_mapping:
            env.vprint(f'loading module "{name}"')
            self.register_module(Module(link, self))
            env.vprint(f'loaded module "{name}"')
        return self._mod_mapping[name]


IncludeInfo = Optional[tuple[str, Header] | Library]


class ModuleState(Enum):
    COMPLETING = 1
    STEADY = 2


class Module:
    def __init__(self, path: str, mgr: DependencyManager) -> None:
        self._path = path
        self._name = _module_name(self.path)
        self._config = load_config(_pretty_path_join(path, env.LOCAL_CONFIG_NAME), nonexist_ok=True)
        env.vprint(f'config for "{self}": {self._config}')
        # register self beforehand to solve cylcic link
        self._mgr = mgr
        mgr.register_module(self)
        self._links : list[Module] = []
        for link in self._config.links:
            self._links.append(mgr.link_module_path(self, link))
        self._libraries : list[Library] = []
        for library in self._config.libraries:
            self._libraries.append(mgr.register_library(library, False))
        self._header_paths, self._source_paths = self._gather_files()
        self._headers_mapping : dict[str, Header] = {}
        self._sources_mapping : dict[str, Source] = {}
        self._state = ModuleState.STEADY

    @property
    def path(self) -> str:
        return self._path

    @property
    def name(self) -> str:
        return self._name

    @property
    def header_paths(self) -> set[str]:
        return self._header_paths

    @property
    def source_paths(self) -> set[str]:
        return self._source_paths

    @property
    def headers(self) -> Iterable[Header]:
        return self._headers_mapping.values()

    @property
    def sources(self) -> Iterable[Source]:
        return self._sources_mapping.values()

    def find_source(self, path: str) -> Optional[Source]:
        target = os.path.normpath(path)
        return self._sources_mapping.get(target)

    def _is_intermedaite(self, parent: str, name: str) -> bool:
        return parent == self._path and name == env.BUILD_DIR_NAME

    def _gather_files(self) -> tuple[set[str], set[str]]:
        hdrs : set[str] = set()
        srcs : set[str] = set()
        q : Queue[str] = Queue()
        q.put(self._path)
        while not q.empty():
            parent = q.get()
            for name in os.listdir(parent):
                if self._is_intermedaite(parent, name):
                    continue
                path = _pretty_path_join(parent, name)
                if os.path.isdir(path):
                    q.put(path)
                    continue
                match get_file_type(name):
                    case FileType.HEADER:
                        hdrs.add(path)
                    case FileType.SOURCE:
                        srcs.add(path)
                    case FileType.UNKNOWN:
                        ...
        return hdrs, srcs

    def _find_self_include(self, include: str) -> Optional[tuple[str, Header]]:
        info : Optional[tuple[str, str]] = None
        for path in self._header_paths:
            suffix = f'/{include}'
            if path == include:
                info = '.', path
            elif path.endswith(suffix):
                info = path[:-len(suffix)], path
        if info is None:
            return None
        return info[0], self._analyse_header(info[1])

    def _find_library_include(self, include: str) -> Optional[Library]:
        for libs in [self._libraries, self._mgr.global_libraries]:
            for lib in libs:
                if lib.pattern.match(include):
                    return lib
        return None

    def _find_link_include(self, include: str) -> IncludeInfo:
        for mod in self._links:
            match = mod._find_self_include(include)
            if match is not None:
                return match
        return None

    def _find_hinclude(self, include: str) -> IncludeInfo:
        info = self._find_link_include(include)
        if info is None:
            return self._find_library_include(include)
        return info

    def _find_qinclude(self, include: str) -> IncludeInfo:
        info = self._find_self_include(include)
        if info is not None:
            return info
        return self._find_hinclude(include)

    def _analyse_file(self, file: str) -> Header | Source:
        hdrs : set[tuple[str, Header]] = set()
        libs : set[Library] = set()
        details = get_compile_details(file)
        infos : list[IncludeInfo] = []
        for hincl in details.hincludes:
            infos.append(self._find_hinclude(hincl))
        for qincl in details.qincludes:
            infos.append(self._find_qinclude(qincl))
        for info in infos:
            if info is None:
                continue
            if isinstance(info, tuple):
                hdrs.add(info)
            else:
                libs.add(info)
        match get_file_type(file):
            case FileType.HEADER:
                return Header(file, details.options, hdrs, libs, None)
            case FileType.SOURCE:
                return Source(file, details.options, hdrs, libs)
            case FileType.UNKNOWN:
                sys_exit(f'unknown file "{file}"')

    def _analyse_header(self, path: str) -> Header:
        if path in self._headers_mapping:
            return self._headers_mapping[path]
        header = cast(Header, self._analyse_file(path))
        self._headers_mapping.setdefault(path, header)
        return header

    def _analyse_source(self, path: str) -> Source:
        if path in self._sources_mapping:
            return self._sources_mapping[path]
        source = cast(Source, self._analyse_file(path))
        self._sources_mapping.setdefault(path, source)
        return source

    def _complete_header_once(self) -> bool:
        changed = False
        for src_path, src in self._sources_mapping.items():
            name = get_file_name(src_path)
            for _, hdr in src.local_headers:
                if hdr.path not in self._headers_mapping or hdr.source is not None:
                    continue
                if name == get_file_name(hdr.path):
                    changed = True
                    hdr.attach_source(src)
        for hdr_path, hdr in self._headers_mapping.items():
            if hdr.source is not None:
                continue
            name = get_file_name(hdr_path)
            for src_path in self._source_paths:
                if name == get_file_name(src_path):
                    changed = True
                    hdr.attach_source(self._analyse_source(src_path))
                    continue
        return changed

    def _complete_header_epoch(self) -> bool:
        self._state = ModuleState.COMPLETING
        changed = False
        while self._complete_header_once():
            changed = True
        for mod in self._links:
            if mod._state == ModuleState.COMPLETING:
                continue
            if mod._complete_header_epoch():
                changed = True
        self._state = ModuleState.STEADY
        return changed

    def _complete_header(self) -> None:
        while self._complete_header_epoch():
            ...

    def analyse_files(self) -> None:
        for header in self._header_paths:
            self._analyse_header(header)
        for source in self._source_paths:
            self._analyse_source(source)
        self._complete_header()

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.name})'
