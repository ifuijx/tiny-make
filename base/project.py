from typing import Optional

from . import env
from .config import Config
from .module import DependencyManager, Module, Source


class Project:
    def __init__(self, config: Config) -> None:
        self._path = env.root()
        self._manager = DependencyManager()
        for lib in config.libraries:
            self._manager.register_library(lib, True)
        self._main = self._manager.link_module_path(None, self._path)
        self._main.analyse_files()

    @property
    def main(self) -> Module:
        return self._main

    def find_source(self, path: str) -> Optional[Source]:
        return self.main.find_source(path)

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self._path})'
