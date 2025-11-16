import os
import re
import tomllib
from dataclasses import dataclass
from typing import Optional

from . import env
from .library import Library
from .utils import sys_exit


@dataclass
class Config:
    optimize: bool
    prefer: str
    links: list[str]
    libraries: list[Library]

    @property
    def options(self) -> list[str]:
        if self.optimize:
            return ['-O3']
        else:
            # TODO: address sanitizer
            # return ['-g', '-O0', '-fno-omit-frame-pointer', '-fsanitize=address']
            return ['-g', '-O0', '-fno-omit-frame-pointer']

    def update(self, config: 'Config') -> None:
        self.optimize = config.optimize
        self.prefer = config.prefer
        self.links.extend(config.links)
        self.libraries.extend(config.libraries)


def default_config() -> Config:
    return Config(False, 'clang++', [], [])


def load_config(path: str, *, nonexist_ok: bool=False) -> Config:
    env.vprint(f'loading config from "{path}"')

    config = default_config()

    if nonexist_ok and not os.path.exists(path):
        return config

    try:
        with open(path, 'rb') as fp:
            content = tomllib.load(fp)
    except Exception:
        sys_exit(f'load config "{path}" failed')

    if 'optimize' in content:
        config.optimize = content['optimize']
    if 'prefer' in content:
        config.prefer = content['prefer']
    if 'dependency' in content:
        dependency = content['dependency']
        if 'links' in dependency:
            config.links.extend(dependency['links'])
        if 'libraries' in dependency:
            for library in  dependency['libraries']:
                if 'name' not in library or 'pattern' not in library:
                    sys_exit(f'parse config {path} failed')
                name = library['name']
                pattern : Optional[re.Pattern[str]] = None
                try:
                    pattern = re.compile(library['pattern'])
                except Exception:
                    sys_exit(f'parse config {path} failed, pattern of library "{name}" is illegal')
                include, libpath, libs = map(library.get, ['include', 'libpath', 'libs'])
                config.libraries.append(Library(name, pattern, include, libpath, libs))

    return config


def global_config() -> Config:
    config = load_config(env.GLOBAL_CONFIG_PATH, nonexist_ok=True)
    config.update(load_config(env.USER_CONFIG_PATH, nonexist_ok=True))
    return config
