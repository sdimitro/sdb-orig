# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from crash.commands.zfs.list import List
from crash.commands.sdb import SDBCommand
from crash.commands.walk import Walker

class MultiList(Walker):
    """ walk multilist """

    cmdName = 'multilist'
    inputType = 'multilist_t *'
    def __init__(self, args = ''):
        super().__init__()

    def walk(self, multilist):
        num_sublists = multilist['ml_num_sublists']
        sublists = multilist['ml_sublists']

        for i in range(num_sublists):
            sublist = sublists[i]['mls_list'].address
            yield from SDBCommand.executePipeline([sublist], [List()])
