# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from crash.commands.sdb import SDBCommand
from crash.commands.locator import Locator
from crash.commands.pretty_printer import PrettyPrinter
from crash.commands.zfs.avl import Avl
from crash.commands.cast import Cast
from crash.commands.zfs.vdev import Vdev
from crash.commands.zfs.metaslab import Metaslab
from crash.commands.zfs.zfs_util import symbol_address

class Spa(Locator, PrettyPrinter):
    cmdName = 'spa'
    inputType = 'spa_t *'
    outputType = 'spa_t *'

    def __init__(self, args=""):
        super().__init__()
        try:
            parser = argparse.ArgumentParser(description = "spa command")
            parser.add_argument('-v', '--vdevs',action='store_true',
                    help='vdevs flag' )
            parser.add_argument('-m', '--metaslab',action='store_true',
                    help='metaslab flag' )
            parser.add_argument('-H', '--histogram',action='store_true',
                    help='histogram flag' )
            parser.add_argument('-w', '--weight',action='store_true',
                    help='weight flag' )
            parser.add_argument('poolnames', nargs='*')
            self.args = parser.parse_args(gdb.string_to_argv(args))
            self.arg_string = ""
            if self.args.metaslab:
                self.arg_string += "-m "
            if self.args.histogram:
                self.arg_string += "-H "
            if self.args.weight:
                self.arg_string += "-w "

        except:
            pass

    def pretty_print(self, spas):
        print("{:14} {}".format("ADDR", "NAME"))
        print("%s" % ('-' * 60))
        for spa in spas:
            print("{:14} {}".format(hex(spa), spa['spa_name'].string()))
            if self.args.vdevs:
                vdevs = SDBCommand.executePipeline(
                        [spa], [Vdev()])
                Vdev(self.arg_string).pretty_print(vdevs, 5)

    def noInput(self):
        input = SDBCommand.executePipeline(
                [symbol_address("spa_namespace_avl")],
                [Avl(), Cast('spa_t *')])
        for spa in input:
            if self.args.poolnames and spa['spa_name'].string() not in self.args.poolnames:
                continue
            yield spa
