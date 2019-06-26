# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
from crash.commands.sdb import PipeableCommand

class Print(PipeableCommand):
    cmdName = 'print'
    gdbCmdName = 'zprint'
    def __init__(self, arg=""):
        super().__init__()
        self.args = arg

    def call(self, input):
        for i in input:
            if i.type.code == gdb.TYPE_CODE_PTR:
                cmd = "(*({}){})".format(i.type, hex(i))
            else:
                cmd = "({}){}".format(i.type, hex(i))
            if len(self.args) > 0:
                cmd += "." + self.args
            yield gdb.parse_and_eval(cmd)
