# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from crash.commands.zfs.zfs_util import symbol_address

from collections import defaultdict

class DBufStats(gdb.Command):
    """ dbuf stats """

    def __init__(self) -> None:
        super(DBufStats, self).__init__('dbuf_stats', gdb.COMMAND_DATA)

    def count_chain(db, chain_depth):
        count = 0
        while db:
            chain_depth[count] += 1
            count += 1
            db = db['db_hash_next']
        return count

    def invoke(self, argstr, from_tty):
        dbuf_hash = symbol_address("dbuf_hash_table")
        table_mask = dbuf_hash['hash_table_mask']
        dbuf_count = symbol_address('dbuf_hash_count').dereference()
        print ("hash table has " + str(table_mask) + " buckets, " +
                str(dbuf_count) + " dbufs (avg " + str(table_mask/dbuf_count) +
                "  buckets/dbuf)")

        bucket_chain_len = defaultdict(int)
        dbuf_chain_depth = defaultdict(int)
        for i in range(0, table_mask):
            dbuf = dbuf_hash['hash_table'][i]
            chainlen = DBufStats.count_chain(dbuf, dbuf_chain_depth)
            bucket_chain_len[chainlen] += 1

        print("{:<20}{}".format("hash chain length", "number of buckets"))
        for len in bucket_chain_len:
            print("{:<20d}{:d}".format(len, bucket_chain_len[len]))

        print("{:<20}{}".format("hash chain depth", "number of dbufs"))
        for depth in dbuf_chain_depth:
            print("{:<20d}{:d} {:d}%".format(depth, dbuf_chain_depth[depth],
                    int(dbuf_chain_depth[depth] * 100 / dbuf_count)))

DBufStats()
