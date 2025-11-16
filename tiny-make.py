#!/bin/env python3

import argparse
import json
import os
import sys

sys.dont_write_bytecode = True

from base import env
from base.cache import clear_cache
from base.compiler import Compiler, select_compiler
from base.config import Config, default_config, global_config
from base.utils import *
from base.project import Project


parser = argparse.ArgumentParser('tiny-make', description='run tiny c++ program')

parser.add_argument('main', nargs='?', help='the main file')
parser.add_argument('args', nargs='*', help='the args for main file')
parser.add_argument('-c', '--compiler', choices=['g++', 'clang++'], default=default_config().prefer, help='which compiler prefered')
parser.add_argument('-d', '--debug', action='store_true', help='use gdb')
parser.add_argument('-p', '--performance', action='store_true', default=False, help='do not use asan')
parser.add_argument('-v', '--verbose', action='store_true', help='show details')
parser.add_argument('--link', action='append', default=[], help='link other projects')
parser.add_argument('--clear', action='store_true', default=False, help='clear compile cache')


def export_compile_commands(project: Project, compiler: Compiler, config: Config) -> None:
    commands = compiler.compile_commands(project.main, config)
    with open('compile_commands.json', 'w') as fp:
        json.dump(commands, fp, indent=4)


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    arg_idx = len(sys.argv)
    for i, _ in enumerate(sys.argv):
        if sys.argv[i].startswith('-'):
            continue
        ns = parser.parse_args(sys.argv[1:i + 1])
        if ns.main:
            arg_idx = i + 1
            break

    ns = parser.parse_args(sys.argv[1:arg_idx])

    return ns, sys.argv[arg_idx:]


if __name__ == '__main__':
    ns, args = parse_args()

    env.set_verbose(ns.verbose)

    config = global_config()
    config.update(Config(ns.performance, ns.compiler, ns.link, []))

    if ns.clear:
        clear_cache()
        exit(0)

    compiler = select_compiler(config.prefer)
    project = Project(config)

    export_compile_commands(project, compiler, config)

    if ns.main:
        source = project.find_source(ns.main)
        if source is None:
            print(f'can not find source file "{ns.main}"', file=sys.stderr)
            exit(1)
        exe = compiler.compile(source, config)
        if ns.debug:
            cprint(f'executing gdb {exe} {" ".join(args)}', Color.GREEN)
            os.execl('/usr/bin/gdb', 'gdb', '--args', exe, *args)
        else:
            cprint(f'executing {exe} {" ".join(args)}', Color.GREEN)
            os.execl(exe, exe, *args)
