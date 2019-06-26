# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from typing import Callable, Any
from crash.commands.zfs.list import LinuxList
from crash.commands.zfs.zfs_util import offsetof,symbol_address
from crash.commands.sdb import SDBCommand
from crash.commands.pipe_utils import LineCount
from crash.commands.cast import Cast

class Kmastat(gdb.Command):
    def __init__(self) -> None:
        super().__init__('kmastat', gdb.COMMAND_DATA)
        parser = argparse.ArgumentParser(description='Print information on each kmem cache')
        parser.add_argument('-k', action='store_true', help='show memory in units of KiB')
        parser.add_argument('-m', action='store_true', help='show memory in units of MiB')
        parser.add_argument('-g', action='store_true', help='show memory in units of GiB')
        self.parser = parser

    def print_cache(self, cache, args):
        if int(cache['skc_linux_cache']) != 0:
            return
        num_complete_slabs = int(next(SDBCommand.executePipeline([cache['skc_complete_list'].address],
                                                             [LinuxList(str(offsetof('spl_kmem_slab_t', 'sks_list'))),
                                                              LineCount()])))
        entries = 0
        for slab in LinuxList(str(offsetof('spl_kmem_slab_t', 'sks_list'))).walk(cache['skc_partial_list'].address):
            cast_slab = slab.cast(gdb.lookup_type('spl_kmem_slab_t').pointer())
            entries += int(cast_slab['sks_ref'])
        entries += num_complete_slabs * int(cache['skc_slab_objs'])
        print('{:25} {:6} {:6} {:6} {:10}{}'.format(cache['skc_name'].string(), int(cache['skc_obj_size']),
                                                    entries, int(cache['skc_obj_total']), 
                                                    int(int(cache['skc_slab_total']) * int(cache['skc_slab_size']) / args.divisor),
                                                    args.suffix))
    def invoke(self, argstr, from_tty):
        try:
            args = self.parser.parse_args(gdb.string_to_argv(argstr))
        except Exception as e:
            print(e)
            self.parser.print_help() #TODO for -h, we end up printing message twice
            return
        if args.k:
            args.divisor = 1024
            args.suffix = 'K'
        elif args.m:
            args.divisor = 1024*1024
            args.suffix = 'M'
        elif args.g:
            args.divisor = 1024*1024*1024
            args.suffix = 'G'
        else:
            args.divisor = 1
            args.suffix = 'B'
            

        print('cache                        buf    buf    buf     memory')
        print('name                        size in use  total     in use')
        print('------------------------- ------ ------ ------ ----------')
        for cache in SDBCommand.executePipeline([symbol_address('spl_kmem_cache_list')],
                                                     [LinuxList(str(offsetof('spl_kmem_cache_t', 'skc_list'))),
                                                      Cast('spl_kmem_cache_t *')]):
            self.print_cache(cache, args)

Kmastat()
