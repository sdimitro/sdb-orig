# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
from crash.commands.sdb import SDBCommand
from crash.commands.walk import Walker
from crash.commands.pretty_printer import PrettyPrinter
from crash.commands import CrashCommandParser
from crash.commands.zfs.list import List
from crash.commands.cast import Cast

def _zio_stage(zio):
    stage = str(zio['io_stage'])
    if not stage.startswith('ZIO_STAGE_'):
        return '? (0x%x)' % zio['io_stage']
    return stage[len('ZIO_STAGE_'):]

def _zio_type(zio):
    ztype = str(zio['io_type'])
    if not ztype.startswith('ZIO_TYPE_'):
        return '? (0x%x)' % zio['io_type']
    return ztype[len('ZIO_TYPE_'):]

def _zio_waiter(zio):
    waiter = '0x%x' % zio['io_waiter']
    if waiter == '0x0':
        waiter = '-'
    return waiter

def _zio_elapsed(zio):
    timestamp = int(zio['io_timestamp'])
    if timestamp == 0:
        return '-'
    # TODO: return elapsed instead of timestamp
    return timestamp

def _print_zio(zio, depth):
    padding = min(depth, Zio.MAX_ADDR_PADDING)
    addr_str = ' ' * padding + '0x%x' % zio
    print('%-*s %-5s %-16s %-18s %-12s'
          % (Zio.ADDR_SPACES, addr_str, _zio_type(zio), _zio_stage(zio),
             _zio_waiter(zio), _zio_elapsed(zio)))


class Zio(Walker, PrettyPrinter):
    """ display single zio or zio tree """

    S_UNDERLINE = '\033[4m'
    S_END = '\033[0m'
    MAX_ADDR_PADDING = 10
    ADDR_SPACES = 18 + 1 + MAX_ADDR_PADDING
    ZIO_TYPE = None

    cmdName = 'zio'
    inputType = 'zio_t *'
    def __init__(self, arg=""):
        super().__init__()

        parser = CrashCommandParser(prog='zio', usage='zio [-cpr]')
        parser.add_argument('-r', dest='recursive', action='store_true')
        parser.add_argument('-c', dest='children', action='store_true')
        parser.add_argument('-p', dest='parents', action='store_true')
        self.args = parser.parse_args(gdb.string_to_argv(arg))

        if self.args.parents:
            self.list_name = 'io_parent_list'
            self.node_name = 'zl_parent'
        else:
            self.list_name = 'io_child_list'
            self.node_name = 'zl_child'

        self.skip_initial = ((self.args.children or self.args.parents) and
                             not self.args.recursive)

    def _walk_impl(self, zio, depth, skip_current=False, doPrint=False):
        #
        # When we print parents or children non-recursively, we want the skip
        # the current node that is provided, so we only traverse once.
        #
        if not skip_current:
            if self.islast and doPrint:
                _print_zio(zio, depth)
            else:
                yield zio

        if self.args.recursive or skip_current:
            new_depth = depth + 1 if not skip_current else 0
            for link in SDBCommand.executePipeline(
                    [zio[self.list_name].address], [List(), Cast('zio_link_t *')]):
                nzio = link[self.node_name]
                yield from self._walk_impl(nzio, new_depth)

    def walk(self, addr, doPrint=False):
        if Zio.ZIO_TYPE is None:
            Zio.ZIO_TYPE = gdb.lookup_type('zio_t').pointer()
        zio = addr.cast(Zio.ZIO_TYPE)

        yield from self._walk_impl(zio, 0, self.skip_initial, doPrint)

    def pretty_print(self, addr):
        _print_zio(zio, 0)

    def call(self, input):
        if self.islast:
            print(Zio.S_UNDERLINE + '%-*s %-5s %-16s %-18s %-12s'
                  % (Zio.ADDR_SPACES, 'ADDRESS', 'TYPE', 'STAGE', 'WAITER',
                     'TIME_ELAPSED') + Zio.S_END)

        for addr in input:
            yield from self.walk(addr, doPrint=True)
