# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from typing import Callable, Any
from crash.commands.zfs.zfs_util import *

#
# TODO: nicenum print the size counters
#
class Arc(gdb.Command):
    def __init__(self) -> None:
        super().__init__("arc", gdb.COMMAND_DATA)

    def print_arc(self, addr):
        stats = addr.dereference()
        for field in stats.type.fields():
            istat = stats[field.name]
            valp = istat['value']
            print("{:32} {} {}".format(istat['name'].string(), "=", valp['ui64']))

    def invoke(self, arg, from_tty):
        print("----------------------------------------")
        self.print_arc(symbol_address("arc_stats"))

Arc()
