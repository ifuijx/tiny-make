import errno
import os
from hashlib import md5

from .utils import *


LOCAL_CONFIG_NAME = '.tiny-make.toml'
GLOBAL_CONFIG_PATH = '/etc/tiny-make/tiny-make.toml'
USER_CONFIG_PATH = os.path.expanduser('~/.cache/tiny-make/tiny-make.toml')

BUILD_DIR_NAME = 'build'
LINKS_DIR_PATH = os.path.join(BUILD_DIR_NAME, '.links')
TINY_MAKE_DIR_NAME = '.tiny-make'
CACHE_FILE_PATH = os.path.join(BUILD_DIR_NAME, TINY_MAKE_DIR_NAME, 'cache.json')


__verbose = False

def set_verbose(verbose: bool) -> None:
    global __verbose
    __verbose = verbose


def vprint(*args: object) -> None:
    if not __verbose:
        return
    output = ' '.join(map(str, args))
    cprint(f'[INFO] {output}', Color.LIGHTGRAY)


def root() -> str:
    return os.getcwd()


def add_link_path(path: str) -> str:
    if not os.path.isdir(path):
        sys_exit(f'link target "{path}" is not a directory', errno.ENOTDIR)

    if os.path.samefile(root(), path):
        return '.'

    try:
        os.makedirs(LINKS_DIR_PATH, exist_ok=True)
    except OSError as e:
        sys_exit(f'create links directory "{LINKS_DIR_PATH}" failed', e.errno)

    name = os.path.split(path)[-1]
    suffix = md5(name.encode()).hexdigest()[:6]
    link = os.path.join(LINKS_DIR_PATH, f'{name}-{suffix}')

    vprint(f'will symlink "{path}" to "{link}"')

    if os.path.exists(link):
        if os.path.samefile(path, link):
            return link
        else:
            sys_exit(f'link target "{path}" already exists', errno.EEXIST)

    try:
        os.symlink(path, link)
    except OSError as e:
        sys_exit(f'failed to create link path "{link}"', e.errno)

    return link
