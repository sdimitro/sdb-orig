# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import traceback
import subprocess
import sys
import shlex

#
# TODO: Comment everywhere once stabilized
#

allSDBCommands = {}

class SDBCommand(object):

    def __init__(self, name):
        self.cmdName = name

    @staticmethod
    def __registerCommand(name, c):
        allSDBCommands[name] = c

    # When a subclass is created we register it in the
    # table of commands.
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.cmdName:
            SDBCommand.__registerCommand(cls.cmdName, cls)

    @classmethod
    def invoke(cls, args):
        print('error: unimplemented command')

class TestCmd(SDBCommand):
    cmdName = "zfs_dbgmsg"

    def __init__(self):
        super().__init__(TestCmd.cmdName)

    @classmethod
    def invoke(cls, argstr):
        print("command output 0")

class EchoCmd(SDBCommand):
    cmdName = "echo"

    def __init__(self):
        super().__init__(TestCmd.cmdName)

    @classmethod
    def invoke(cls, args):
        print("args: " + str(args))
