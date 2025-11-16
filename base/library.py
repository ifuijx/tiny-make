import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class Library:
    name: str
    pattern: re.Pattern[str]
    include: Optional[str]
    libpath: Optional[str]
    libs: Optional[list[str]]

    def __hash__(self) -> int:
        return hash(self.name)

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.name})'
