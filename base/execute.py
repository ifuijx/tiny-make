import subprocess
import sys
from typing import cast

from .utils import *


def _proc_outputs(proc: subprocess.Popen[bytes]) -> tuple[Optional[str], Optional[str]]:
    if proc.poll() is None:
        raise Exception
    stdout, stderr = proc.communicate()
    if isinstance(stdout, bytes):
        stdout = stdout.decode('utf-8')
    if isinstance(stderr, bytes):
        stderr = stderr.decode('utf-8')
    return stdout, stderr   # type: ignore


def foreground_execute_handle(*args: str) -> subprocess.Popen[bytes]:
    cprint(f'executing {" ".join(args)}', Color.GREEN)
    return subprocess.Popen(args)


def wait_for_handles(procs: list[subprocess.Popen[bytes]]) -> None:
    errs : list[tuple[int, list[str], Optional[str]]] = []
    for proc in procs:
        if errs:
            ret = proc.poll()
            if ret is None:
                proc.kill()
                proc.wait()
            elif ret != 0:
                errs.append((ret, proc.args, _proc_outputs(proc)[1]))  # type: ignore
        else:
            proc.communicate()
            if proc.returncode != 0:
                errs.append((proc.returncode, proc.args, _proc_outputs(proc)[1]))   # type: ignore

    if not errs:
        return

    for errno, args, stderr in errs:
        command = ' '.join(args)
        cprint(f'execute "{command}" failed, returns {errno}', Color.RED)
        if stderr is not None:
            print(stderr, file=sys.stderr)

    sys_exit('compilation stopped')


def foreground_execute(*args: str) -> None:
    proc = foreground_execute_handle(*args)
    proc.communicate()
    if proc.returncode:
        sys_exit(None, proc.returncode)


def background_execute(command: str) -> tuple[str, str]:
    proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc.communicate()
    stdout, stderr = _proc_outputs(proc)
    stdout = cast(str, stdout)
    stderr = cast(str, stderr)
    if proc.returncode:
        cprint(f'execute "{command}" failed, returns {proc.returncode}', Color.RED)
        print(stderr, file=sys.stderr)
        sys_exit(None, proc.returncode)
    return stdout, stderr
