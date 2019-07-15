#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
XXX
"""

import drgn
import sys
from sdb.repl import REPL
from sdb.command import allSDBCommands

def main():
    prog = drgn.Program()
    prog.set_kernel()
    try:
        prog.load_default_debug_info()
    except drgn.MissingDebugInfoError as e:
        print(str(e), file=sys.stderr)
    repl = REPL(prog, allSDBCommands)
    repl.run()

if __name__ == '__main__':
    main()
