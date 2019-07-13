# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from typing import Callable, Any
from crash.commands.sdb import PipeableCommand
from crash.commands.zfs.zfs_util import parse_type

class Cast(PipeableCommand):
    """ walk list """

    cmdName = 'cast'
    def __init__(self, arg : str = "") -> None:
        super().__init__()

        try:
            parser = argparse.ArgumentParser(prog='cast')
            parser.add_argument('cast_type', default=['void', '*'], nargs='+')
            self.args = parser.parse_args(gdb.string_to_argv(arg))
        except:
            pass

        self.args.cast_type = parse_type(' '.join(self.args.cast_type))

    def call(self, input):
        for listaddr in input:
            yield listaddr.cast(self.args.cast_type)
