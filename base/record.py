from dataclasses import dataclass


@dataclass
class Record:
    target: str
    args: list[str]
    dependencies: list[str]

    @property
    def command(self) -> str:
        return ' '.join(self.args)

