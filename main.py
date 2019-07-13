#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
XXX
"""

from sdb.repl import REPL
from sdb.command import allSDBCommands

def main():
    repl = REPL(allSDBCommands)
    repl.run()

if __name__ == '__main__':
    main()
