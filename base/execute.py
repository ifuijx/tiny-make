import subprocess
import sys
from typing import overload

from .utils import *


def _proc_outputs(proc: subprocess.Popen[bytes]) -> tuple[str, str]:
    if proc.poll() is None:
        raise Exception
    stdout, stderr = proc.communicate()
    if isinstance(stdout, bytes):
        stdout = stdout.decode('utf-8')
    if isinstance(stderr, bytes):
        stderr = stderr.decode('utf-8')
    return stdout, stderr   # type: ignore


@overload
def foreground_execute_handle(executable: str, *args: str) -> subprocess.Popen[bytes]:
    ...


@overload
def foreground_execute_handle(command: str) -> subprocess.Popen[bytes]:
    ...


def foreground_execute_handle(*args: str) -> subprocess.Popen[bytes]:   # type: ignore
    if len(args) == 1:
        command = args[0]
    else:
        command = ' '.join(args)
    cprint(f'executing {command}', Color.GREEN)
    return subprocess.Popen(command, shell=True)


def wait_for_handles(procs: list[subprocess.Popen[bytes]]) -> None:
    errs : list[tuple[int, str, str]] = []
    for proc in procs:
        if errs:
            ret = proc.poll()
            if ret is None:
                proc.kill()
            elif ret != 0:
                errs.append((ret, proc.args, proc.stderr, _proc_outputs(proc)[1]))  # type: ignore
        else:
            proc.communicate()
            if proc.returncode != 0:
                errs.append((proc.returncode, proc.args, _proc_outputs(proc)[1]))   # type: ignore

    if not errs:
        return

    for errno, command, stderr in errs:
        cprint(f'execute "{command}" failed, returns {errno}', Color.RED)
        print(stderr, file=sys.stderr)

    sys_exit('compilation stopped')


@overload
def foreground_execute(executable: str, *args: str) -> None:
    ...


@overload
def foreground_execute(command: str) -> None:
    ...


def foreground_execute(*args: str) -> None: # type: ignore
    proc = foreground_execute_handle(*args)
    proc.communicate()
    if proc.returncode:
        sys_exit(None, proc.returncode)


def background_execute(command: str) -> tuple[str, str]:
    proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc.communicate()
    stdout, stderr = _proc_outputs(proc)
    if proc.returncode:
        cprint(f'execute "{command}" failed, returns {proc.returncode}', Color.RED)
        print(stderr, file=sys.stderr)
        sys_exit(None, proc.returncode)
    return stdout, stderr
