# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from crash.commands.zfs.zfs_util import symbol_address
from crash.commands.sdb import SDBCommand
from crash.commands.locator import Locator
from crash.commands.locator import InputHandler
from crash.commands.pretty_printer import PrettyPrinter
from crash.commands.walk import Walk
from crash.commands.cast import Cast
from typing import Iterable

class DslDir():
    # dd is gdb.Value of type dsl_dir_t*
    def name(dd):
        pname = ''
        if dd['dd_parent']:
            pname = DslDir.name(dd['dd_parent']) + '/'
        return pname + dd['dd_myname'].string()

class Dataset():
    # ds is gdb.Value of type dsl_dataset_t*
    def name(ds):
        if ds == 0:
            return 'MOS'
        name = DslDir.name(ds['ds_dir'])
        if not ds['ds_prev']:
            sn = ds['ds_snapname'].string()
            if len(sn) == 0:
                sn = '%UNKNOWN_SNAP_NAME%'
            name += '@' + sn
        return name

class Objset():
    # os is gdb.Value of type objset_t*
    def name(os):
        return Dataset.name(os['os_dsl_dataset'])

class Dbuf(Locator, PrettyPrinter):
    cmdName = 'dbuf'
    inputType = 'dmu_buf_impl_t *'
    outputType = 'dmu_buf_impl_t *'

    def __init__(self, arg=""):
        super().__init__()
        parser = argparse.ArgumentParser(prog='dbuf')
        parser.add_argument('-o', '--object', type=int,
                help='filter: only dbufs of this object' )
        parser.add_argument('-l', '--level', type=int,
                help='filter: only dbufs of this level' )
        parser.add_argument('-b', '--blkid', type=int,
                help='filter: only dbufs of this blkid' )
        parser.add_argument('-d', '--dataset', type=str,
                help='filter: only dbufs of this dataset name (or "MOS")' )
        parser.add_argument('-H', '--has-holds', action='store_true',
                help='filter: only dbufs that have nonzero holds' )
        try:
            self.args = parser.parse_args(gdb.string_to_argv(arg))
        except:
            pass

    def pretty_print(self, dbufs):
        print ("{:>20} {:>8} {:>4} {:>8} {:>5} {}".format("addr",
            "object", "lvl", "blkid", "holds", "os"))
        for dbuf in dbufs:
            print ("{:>20} {:>8d} {:>4d} {:>8d} {:>5d} {}".format(
                hex(dbuf),
                int(dbuf['db']['db_object']),
                int(dbuf['db_level']),
                int(dbuf['db_blkid']),
                int(dbuf['db_holds']['rc_count']),
                Objset.name(dbuf['db_objset'])))

    def filter(self, db):
        if self.args.object and db['db']['db_object'] != self.args.object:
            return False
        if self.args.level and db['db_level'] != self.args.level:
            return False
        if self.args.blkid and db['db_blkid'] != self.args.blkid:
            return False
        if self.args.has_holds and db['db_holds']['rc_count'] == 0:
            return False
        if self.args.dataset and Objset.name(db['db_objset']) != self.args.dataset:
            return False
        return True

    # dn is gdb.Value of type dnode_t*
    # need to yield gdb.Value's of type dmu_buf_impl_t*
    @InputHandler('dnode_t*')
    def from_dnode(self, dn : gdb.Value) -> Iterable[gdb.Value]:
        assert dn['dn_dbufs'].address is not None
        for db in SDBCommand.executePipeline(
                [dn['dn_dbufs'].address],
                [Walk(), Cast('dmu_buf_impl_t*')]):
            yield db

    #@InputHandler(None)
    def noInput(self):
        dbuf_hash = symbol_address("dbuf_hash_table")
        mask = dbuf_hash['hash_table_mask']
        table = dbuf_hash['hash_table']

        for i in range(0, mask):
            db = table[i]
            while db:
                if self.filter(db):
                    yield db
                db = db['db_hash_next']
