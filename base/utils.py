from enum import Enum
from typing import NoReturn, Optional


__DEFAULT_ERRNO = -1


def sys_exit(msg: Optional[str], err: Optional[int] = None) -> NoReturn:
    global __DEFAULT_ERRNO

    if msg is not None:
        print(msg)
    if err is None:
        exit(__DEFAULT_ERRNO)
    else:
        exit(err)


class Color(Enum):
    BLACK = 0
    RED = 1
    GREEN = 2
    YELLOW = 3
    BLUE = 4
    MAGENTA = 5
    CYAN = 6
    LIGHTGRAY = 7


def cprint(s: str, foreground: Optional[Color]=None, background: Optional[Color]=None) -> None:
    formats : list[str] = []
    if foreground is not None:
        formats.append(str(foreground.value + 30))
    if background is not None:
        formats.append(str(background.value + 40))

    format = ';'.join(formats)
    if format:
        print(f'\033[{format}m{s}\033[0m')
    else:
        print(s)
