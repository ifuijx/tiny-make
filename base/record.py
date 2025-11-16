from dataclasses import dataclass


@dataclass
class Record:
    target: str
    command: str
    dependencies: list[str]

