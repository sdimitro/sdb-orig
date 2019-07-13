# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from crash.commands.zfs.zfs_util import symbol_address

class Dbufs(gdb.Command):
    """ list dbufs """

    def __init__(self) -> None:
        super().__init__('dbuf_list', gdb.COMMAND_DATA)


    def print_dbuf_chain(dbuf):
        dbuf_impl_type = gdb.lookup_type('struct dmu_buf_impl').pointer()
        db = dbuf.cast(dbuf_impl_type)
        while db :
            print (db)
            db = db['db_hash_next'].cast(dbuf_impl_type)


    def print_dbufs(hash_map):
        dbuf_hash_type = gdb.lookup_type('struct dbuf_hash_table').pointer()
        dbuf_hash = hash_map.cast(dbuf_hash_type)
        table_mask = dbuf_hash['hash_table_mask']

        for i in range(0,table_mask):
            dbuf = dbuf_hash['hash_table'][i]
            if dbuf:
                Dbufs.print_dbuf_chain(dbuf)

    def invoke(self, argstr, from_tty):
         Dbufs.print_dbufs(symbol_address("dbuf_hash_table"))
Dbufs()
