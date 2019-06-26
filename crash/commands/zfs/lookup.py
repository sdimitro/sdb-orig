# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from typing import Callable, Any
from crash.commands.sdb import PipeableCommand
from crash.commands.zfs.zfs_util import symbol_address

class Lookup(PipeableCommand):

    cmdName = 'lookup'
    def __init__(self, arg=""):
        super().__init__()

        try:
            parser = argparse.ArgumentParser(prog='lookup')
            parser.add_argument('symbol', default=['void', '*'], nargs='+')
            self.args = parser.parse_args(gdb.string_to_argv(arg))
        except:
            pass

    def call(self, input):
        if isinstance(input, list) and len(input) == 0:
            input = self.args.symbol
        for sym in input:
            yield symbol_address(sym)
