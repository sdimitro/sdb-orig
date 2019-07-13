# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from crash.commands.sdb import SDBCommand
from crash.commands.locator import Locator
from crash.commands.locator import InputHandler
from crash.commands.pretty_printer import PrettyPrinter
from typing import Callable, Any, Iterable
from crash.commands.zfs.zfs_util import enum_lookup
from crash.commands.zfs.metaslab import Metaslab

class Vdev(Locator, PrettyPrinter):
    cmdName = 'vdev'
    inputType = 'vdev_t *'
    outputType = 'vdev_t *'

    def __init__(self, args = ""):
        super().__init__()

        # XXX add flag for "direct children (from vdev) only"?
        # XXX add flag for "top level vdevs (from spa) only"?
        try:
            parser = argparse.ArgumentParser(description = "vdev command")
            parser.add_argument('-m', '--metaslab',action='store_true',
                    default=False, help='metaslab flag' )
            parser.add_argument('-H', '--histogram',action='store_true',
                    default=False, help='histogram flag' )
            parser.add_argument('-w', '--weight',action='store_true',
                    default=False, help='weight flag' )
            parser.add_argument('vdev_ids', nargs='*', type=int)
            self.args = parser.parse_args(gdb.string_to_argv(args))
            self.arg_string = ""
            if self.args.histogram:
                self.arg_string += "-H "
            if self.args.weight:
                self.arg_string += "-w "
        except:
            pass

    # arg is iterable of gdb.Value of type vdev_t*
    def pretty_print(self, vdevs, indent=0):
        print("".ljust(indent), "ADDR".ljust(18), "STATE".ljust(7),
                "AUX".ljust(4), "DESCRIPTION")
        print("".ljust(indent), "-" * 60)

        for vdev in vdevs:
            level = 0
            pvd = vdev['vdev_parent']
            while pvd:
                level += 2
                pvd = pvd['vdev_parent']

            if vdev['vdev_path'] != 0:
                print("".ljust(indent), hex(vdev).ljust(18),
                     enum_lookup('vdev_state_t', vdev['vdev_state']).ljust(7),
                     enum_lookup('vdev_aux_t',
                        vdev['vdev_stat']['vs_aux']).ljust(4),
                     "".ljust(level),
                     vdev['vdev_path'].string())

            else:
                print("".ljust(indent), hex(vdev).ljust(18),
                     enum_lookup('vdev_state_t', vdev['vdev_state']).ljust(7),
                     enum_lookup('vdev_aux_t',
                        vdev['vdev_stat']['vs_aux']).ljust(4),
                     "".ljust(level),
                     vdev['vdev_ops']['vdev_op_type'].string())
            if self.args.metaslab:
                metaslabs = SDBCommand.executePipeline( [vdev], [Metaslab()])
                Metaslab(self.arg_string).pretty_print(metaslabs, indent + 5)


    # arg is gdb.Value of type spa_t*
    # need to yield gdb.Value's of type vdev_t*
    @InputHandler('spa_t*')
    def from_spa(self, spa : gdb.Value) -> Iterable[gdb.Value]:
        if self.args.vdev_ids:
            # yield the requested top-level vdevs
            for id in self.args.vdev_ids:
                if id >= spa['spa_root_vdev']['vdev_children']:
                    raise TypeError('vdev id {} not valid; there are only {} vdevs in {}'.format(
                        id,
                        spa['spa_root_vdev']['vdev_children'],
                        spa['spa_name'].string()))
                yield spa['spa_root_vdev']['vdev_child'][id]
        else:
            yield from self.from_vdev(spa['spa_root_vdev'])

    # arg is gdb.Value of type vdev_t*
    # need to yield gdb.Value's of type vdev_t*
    @InputHandler('vdev_t*')
    def from_vdev(self, vdev : gdb.Value) -> Iterable[gdb.Value]:
        if self.args.vdev_ids:
            raise TypeError('when providing a vdev, specific child vdevs can not be requested')
        yield vdev
        for cid in range(0, int(vdev['vdev_children'])):
            cvd = vdev['vdev_child'][cid]
            yield from self.from_vdev(cvd)
