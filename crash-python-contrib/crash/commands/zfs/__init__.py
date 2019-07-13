# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import os
import glob

def discover():
    modules = glob.glob(os.path.dirname(__file__)+"/[A-Za-z]*.py")
    __all__ = [os.path.basename(f)[:-3] for f in modules]
    print(modules)
    mods = __all__
    for mod in mods:
        x = importlib.import_module("crash.commands.{}".format(mod))
