# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
from typing import Callable, Any
from crash.commands.zfs.zfs_util import symbol_address
from crash.commands.zfs.list import List
from crash.commands.cast import Cast
from crash.commands.sdb import SDBCommand
import datetime,getopt

class ZfsDbgmsgArg():
    ts : bool= False
    addr : bool = False
    def __init__(self, ts: bool = False, addr : bool = False):
        self.ts = ts
        self.addr = addr

class ZfsDbgmsg(gdb.Command):
    def __init__(self) -> None:
        super().__init__("zfs_dbgmsg", gdb.COMMAND_DATA)

    # node is a zfs_dbgmsg_t*
    @staticmethod
    def print_msg(node : gdb.Value, ts : bool = False, addr : bool = False) -> None:
        strlen = int(node['zdm_size']) - node.type.target().sizeof
        if addr:
            print("{} ".format(hex(node)), end="") # type: ignore
        if ts:
            timestamp = datetime.datetime.fromtimestamp(int(node['zdm_timestamp']))
            print("{}: ".format(timestamp.strftime('%Y-%m-%dT%H:%M:%S')), end="")

        print("{}".format(node['zdm_msg'].string(encoding='utf-8', length=strlen)))

    def invoke(self, arg : str, from_tty : bool) -> None:
        print(arg)
        optlist, args = getopt.getopt(arg.split(), 'v')
        verbosity = 0
        if len(args) != 0:
            print("Improper arguments to ::zfs_dbgmsg: {}\n".format(args))
            return
        for (opt, arg) in optlist:
            if opt != '-v':
                print ("Improper flag to ::zfs_dbgmsg: {}\n".format(opt))
                return
            elif arg != '':
                print ("Improper value to ::zfs_dbgmsg: {}\n".format(arg))
                return
            verbosity += 1

        proc_list = symbol_address("zfs_dbgmsgs")
        assert proc_list is not None
        list_addr = proc_list['pl_list'].address
        assert list_addr is not None
        for node in SDBCommand.executePipeline([list_addr], [List(), Cast('zfs_dbgmsg_t *')]):
            ZfsDbgmsg.print_msg(node, verbosity >=1, verbosity >= 2)

ZfsDbgmsg()
