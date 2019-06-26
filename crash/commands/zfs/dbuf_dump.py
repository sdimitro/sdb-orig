# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse

class DBuf(gdb.Command):
    """ dbuf fields"""

    def __init__(self) -> None:
        super(DBuf, self).__init__('dbuf_dump', gdb.COMMAND_DATA)

    def invoke(self, argstr, from_tty):
        parser = argparse.ArgumentParser(prog='dbuf_dump')
        parser.add_argument('addr')
        args = parser.parse_args(gdb.string_to_argv(argstr))
        dbuf_addr = gdb.Value(int(args.addr, 0))
        dbuf_impl = dbuf_addr.cast(
                gdb.lookup_type('struct dmu_buf_impl').pointer())
        dbuf = dbuf_addr.cast(gdb.lookup_type('struct dmu_buf').pointer())

        print ("{:>20} {:>8} {:>4} {:>8} {:>5} {:>20}".format("addr",
            "object", "lvl", "blkid", "holds", "os"))
        print ("{:>20} {:>8d} {:>4d} {:>8d} {:>5d} {:>20}".format(
            hex(dbuf_addr),
            int(dbuf['db_object']),
            int(dbuf_impl['db_level']),
            int(dbuf_impl['db_blkid']),
            int(dbuf_impl['db_holds']['rc_count']),
            hex(dbuf_impl['db_objset'])))
DBuf()
