# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from crash.commands.walk import Walker

class Avl(Walker):
    """ walk avl tree """

    cmdName = 'avl'
    inputType = 'avl_tree_t *'
    def __init__(self, arg : str = "") -> None:
        super().__init__()

    def walk(self, tree):
        offset = int(tree['avl_offset'])
        root = tree['avl_root']
        yield from Avl.helper(root, offset)

    def helper(node, offset):
        if node == 0:
            return
        lchild = node.dereference()['avl_child'][0]
        yield from Avl.helper(lchild, offset)

        yield gdb.Value(int(node) - offset).cast(gdb.lookup_type('void').pointer())

        rchild = node.dereference()['avl_child'][1]
        yield from Avl.helper(rchild, offset)
