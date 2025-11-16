import json
import os
import socket
from typing import TypedDict

from . import env
from .record import Record
from .utils import *


class EntryDict(TypedDict):
    hostname: str
    command: str
    dependencies: list[str]


class Cache:
    def __init__(self) -> None:
        self._cache_file = env.CACHE_FILE_PATH

        env.vprint(f'loading cache from "{self._cache_file}"')
        try:
            if os.path.exists(self._cache_file):
                with open(self._cache_file) as fp:
                    self._entries = json.load(fp)
            else:
                self._entries : dict[str, EntryDict] = {}
        except Exception:
            sys_exit(f'load cache file "{self._cache_file}" failed')

    def save(self, records: list[Record]) -> None:
        os.makedirs(os.path.dirname(self._cache_file), exist_ok=True)
        env.vprint(f'saving cache to "{self._cache_file}"')
        cache : dict[str, EntryDict] = {
                record.target: {
                    'hostname': socket.gethostname(),
                    'command': record.command,
                    'dependencies': record.dependencies,
                } for record in records
            }
        self._entries.update(cache)
        try:
            with open(self._cache_file, 'w', encoding='utf-8') as fp:
                json.dump(self._entries, fp, indent=4)
        except OSError as e:
            sys_exit(f'save cahe file "{self._cache_file}" failed', e.errno)

    def has_cache(self, record: Record) -> bool:
        if not os.path.exists(record.target):
            return False

        if record.target not in self._entries:
            return False

        entry = self._entries[record.target]

        if entry['hostname'] != socket.gethostname() or entry['command'] != record.command:
            return False

        if set(record.dependencies) != set(entry['dependencies']):
            return False

        ctime = os.stat(record.target).st_ctime_ns
        for file in record.dependencies:
            if os.stat(file).st_ctime_ns > ctime:
                return False

        return True


def clear_cache() -> None:
    file = env.CACHE_FILE_PATH
    env.vprint(f'removing cache file "{file}"')
    try:
        if os.path.exists(file):
            os.remove(file)
    except OSError as e:
        sys_exit(f'remove cache file "{file}" failed', e.errno)
