import os
import re
from dataclasses import dataclass
from enum import Enum
from queue import Queue
from typing import Optional

from . import env
from .library import Library


class FileType(Enum):
    HEADER = 1
    SOURCE = 2
    UNKNOWN = 3


def get_file_type(name: str) -> FileType:
    _HEADER_PREFIXES = ['.h', '.hpp']
    _SOURCE_PREFIXES = ['.cpp', '.cc', '.cxx']

    if any(name.endswith(p) for p in _HEADER_PREFIXES):
        return FileType.HEADER
    elif any(name.endswith(p) for p in _SOURCE_PREFIXES):
        return FileType.SOURCE
    else:
        return FileType.UNKNOWN


def get_file_name(path: str) -> str:
    return os.path.splitext(os.path.split(path)[1])[0]


@dataclass
class CompileDetails:
    hincludes : list[str]
    qincludes : list[str]
    options: list[str]


__HINCLUDE_DIRECTIVE_PATTERN = re.compile(r'#include\s+<(?P<path>[^>]+)>')
__QINCLUDE_DIRECTIVE_PATTERN = re.compile(r'#include\s+"(?P<path>[^"]+)"')
__OPTIONS_PATTERN = re.compile(r'//\s*TNC:\s*(?P<options>.*)')


def get_compile_details(path: str) -> CompileDetails:
    hincls : list[str] = []
    qincls : list[str] = []
    opts : list[str] = []
    with open(path, 'r', encoding='utf-8') as fp:
        for line in fp:
            content = line.lstrip()
            if content.startswith('#'):
                qmatch = __QINCLUDE_DIRECTIVE_PATTERN.match(content)
                if qmatch:
                    qincls.append(qmatch.group('path'))
                hmatch = __HINCLUDE_DIRECTIVE_PATTERN.match(content)
                if hmatch:
                    hincls.append(hmatch.group('path'))
            elif content.startswith('//'):
                omatch = __OPTIONS_PATTERN.match(content)
                if omatch:
                    opts.extend(omatch.group('options').split())
    return CompileDetails(hincls, qincls, opts)


HeaderDetail = tuple[str, 'Header']


class File:
    def __init__(self, path: str, opts: list[str], header_details: set[HeaderDetail], libs: set[Library]) -> None:
        self._path = path
        self._local_opts = opts
        self._local_header_details = header_details
        self._local_libs = libs

    @property
    def path(self) -> str:
        return self._path

    @property
    def local_headers(self) -> set[HeaderDetail]:
        return self._local_header_details

    # TODO: use functools cache
    @property
    def includes(self) -> set[str]:
        incls : set[str] = set()
        for incl, header in self._local_header_details:
            incls.add(incl)
            incls.update(header.includes)
        for lib in self._local_libs:
            if lib.include is not None:
                incls.add(lib.include)
        if '.' in incls:
            incls.remove('.')
        return incls

    def headers(self) -> set['Header']:
        hdrs : set[Header] = set()
        for _, hdr in self._local_header_details:
            hdrs.add(hdr)
            hdrs.update(hdr.headers())
        return hdrs

    def sources(self) -> set['Source']:
        srcs : set[Source] = set()
        for _, hdr in self._local_header_details:
            srcs.update(hdr.sources())
        return srcs

    def options(self) -> set[str]:
        opts : set[str] = set()
        opts.update(self._local_opts)
        for _, hdr in self._local_header_details:
            opts.update(hdr.options())
        return opts


class Source(File):
    def __init__(self, path: str, opts: list[str], header_details: set[HeaderDetail], libs: set[Library]) -> None:
        super().__init__(path, opts, header_details, libs)

    @property
    def target(self) -> str:
        if self._path.startswith(env.LINKS_DIR_PATH):
            stem = self._path[len(env.LINKS_DIR_PATH) + 1:]
        else:
            stem = self._path
        o = f'{os.path.splitext(stem)[0]}.o'
        return os.path.join(env.BUILD_DIR_NAME, o)

    # override
    def sources(self) -> set['Source']:
        srcs = super().sources()
        if self in srcs:
            srcs.remove(self)
        return srcs

    def libraries(self) -> set[Library]:
        libs : set[Library] = set()
        files : Queue[File] = Queue()
        visited : set[File] = set()
        files.put(self)
        while not files.empty():
            file = files.get()
            visited.add(file)
            libs.update(file._local_libs)
            for _, hdr in file._local_header_details:
                if hdr not in visited:
                    files.put(hdr)
            if isinstance(file, Header) and file.source is not None:
                if file.source not in visited:
                    files.put(file.source)
        return libs

    # override
    def options(self) -> set[str]:
        opts = super().options()
        opts.update(self._local_opts)
        return opts

    def __hash__(self) -> int:
        return hash(self._path)

    def __repr__(self) -> str:
        hdrs = ''.join(f'[{header[1]._path}]' for header in self._local_header_details)
        libs = ''.join(f'<{library.name}>' for library in self._local_libs)
        return f'{self.__class__.__name__}({self._path}){hdrs}{libs}'


class Header(File):
    def __init__(self, path: str, opts: list[str], hdr: set[tuple[str, 'Header']], libs: set[Library], source: Optional[Source]) -> None:
        super().__init__(path, opts, hdr, libs)
        self._source = source

    @property
    def source(self) -> Optional[Source]:
        return self._source

    def attach_source(self, source: Source) -> None:
        self._source = source

    # override
    def sources(self) -> set['Source']:
        srcs = super().sources()
        if self._source is not None:
            srcs.add(self._source)
        return srcs

    def __hash__(self) -> int:
        return hash(self._path)

    def __repr__(self) -> str:
        hdrs = ''.join(f'[{hdr[1]._path}]' for hdr in self._local_header_details)
        libs = ''.join(f'<{lib.name}>' for lib in self._local_libs)
        if self._source is None:
            return f'{self.__class__.__name__}({self._path}){hdrs}{libs}'
        return f'{self.__class__.__name__}({self._path}, {self._source._path}){hdrs}{libs}'
