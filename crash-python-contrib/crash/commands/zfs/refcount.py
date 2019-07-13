# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from typing import Callable, Any
from crash.commands.pretty_printer import PrettyPrinter
from crash.commands.zfs.list import List

class Refcount(PrettyPrinter):
    cmdName = 'refcount'
    inputType = 'zfs_refcount_t *'
    def __init__(self, arg=""):
        super().__init__()
        parser = argparse.ArgumentParser(description = "print refcounts")
        parser.add_argument('-r', '--removed',action='store_true',
                            help='print removed refcounts' )
        self.args = parser.parse_args(gdb.string_to_argv(arg))
        
    def print_reference(self, ref, removed=False):
        print('{}reference with count={:d} with tag {}'.format(('removed ' if removed else ''), cast_ref['ref_number'],
                                                               hex(cast_ref['ref_holder'])))
        
    def pretty_print(self, refcnts):
        for refcnt in refcnts:
            if not hasattr(self.args, 'debug'):
                self.args.debug = False
                for field in gdb.lookup_type('zfs_refcount_t'):
                    if field.name != 'rc_count':
                        self.args.debug = True
                        break
            print('zfs_refcount_t at {} has {:d} holds{} ({})'.format(hex(refcnt), int(refcnt['rc_count']),
                                                                      (', {:d} removed'.format(refcnt['rc_removed_count']) if self.args.removed else ''),
                                                                      ('tracked' if self.args.debug and refcnt['rc_tracked'] else 'untracked')))
            if not self.args.debug or not refcnt['rc_tracked']:
                return

            for ref in List().walk(refcnt['rc_list']):
                cast_ref = ref.cast(gdb.lookup_type('reference_t')).pointer()
                self.print_reference(cast_ref)
            if not self.args.removed:
                return

            print('released holds:')
            for ref in List().walk(refcnt['rc_removed']):
                cast_ref = ref.cast(gdb.lookup_type('reference_t')).pointer()
                self.print_reference(cast_remove, removed=True)
