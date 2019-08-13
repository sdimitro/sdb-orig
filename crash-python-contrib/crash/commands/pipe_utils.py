# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

from crash.commands.sdb import allSDBCommands
from crash.commands.sdb import PipeableCommand
import gdb
from typing import Iterable,Deque
import argparse

class Pipe(gdb.Command):
    def __init__(self) -> None:
        super().__init__('pipe', gdb.COMMAND_DATA)

    def invoke(self, argstr, from_tty):
        print("pipeable commands:")
        for cmd in sorted (allSDBCommands.keys()):
            print("    ", cmd)
Pipe()

class LineCount(PipeableCommand):
    cmdName = 'wc'
    def __init__(self, arg : str = "") -> None:
        super().__init__()
    def call(self, input : Iterable[gdb.Value]) -> Iterable[gdb.Value]:
        i = 0
        for o in input:
            i += 1
        yield gdb.Value(i)

class Filter(PipeableCommand):
    cmdName = 'filter'
    def __init__(self, arg=""):
        super().__init__()
        self.args = arg

    def call(self, input : Iterable[gdb.Value]) -> Iterable[gdb.Value]:
        for i in input:
            if i.type.code == gdb.TYPE_CODE_PTR:
                cmd = "(({}){})->{}".format(i.type, hex(i), self.args) # type: ignore
            else:
                cmd = "(({}){}).{}".format(i.type, hex(i), self.args) # type: ignore
            #print(cmd)
            if (int(gdb.parse_and_eval(cmd)) != 0):
                yield i

class Null(PipeableCommand):
    cmdName = 'null'
    def __init__(self, arg=""):
        super().__init__()

    def call(self, input : Iterable[gdb.Value]) -> Iterable[gdb.Value]:
        for i in input:
            pass
        return []

class Array(PipeableCommand):
    cmdName = 'array'
    def __init__(self, arg : str = ""):
        super().__init__()
        try:
            parser = argparse.ArgumentParser(prog='array')
            # TODO allow 'count' to be omitted if input type is proper array
            parser.add_argument('count', type=int, nargs='?')
            self.args = parser.parse_args(gdb.string_to_argv(arg))
        except:
            pass

    def call(self, input : Iterable[gdb.Value]) -> Iterable[gdb.Value]:
        for array_start in input:
            for idx in range(self.args.count):
                yield array_start + idx
