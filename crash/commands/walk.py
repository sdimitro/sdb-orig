# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
from crash.commands.sdb import SDBCommand, PipeableCommand
from crash.commands.zfs.zfs_util import parse_type
from typing import Iterable, Dict, Type

#
# Commands that are designed to iterate over data structures that can contain
# arbitrary data types.
#
class Walker(PipeableCommand):
    allWalkers : Dict[str, Type["Walker"]] = {}
    def __init__(self) -> None:
        super().__init__()

    # When a subclass is created, register it
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        assert cls.inputType is not None
        Walker.allWalkers[cls.inputType] = cls

    def walk(self, input : gdb.Value) -> Iterable[gdb.Value]:
        raise NotImplementedError

    # Iterate over the inputs and call the walk command on each of them,
    # verifying the types as we go.
    def call(self, input : Iterable[gdb.Value]) -> Iterable[gdb.Value]:
        assert self.inputType is not None
        t = parse_type(self.inputType)
        for i in input:
            if i.type != t:
                raise TypeError('command "{}" does not handle input of type {}'.format(
                    self.cmdName,
                    i.type))

            yield from self.walk(i)

# A convenience command that will automatically dispatch to the appropriate
# walker based on the type of the input data.
class Walk(PipeableCommand):
    cmdName = 'walk'
    def __init__(self, arg : str = "") -> None:
        super().__init__()

    def call(self, input : Iterable[gdb.Value]) -> Iterable[gdb.Value]:
        baked = [ (parse_type(k), c) for k, c in Walker.allWalkers.items() ]
        hasInput = False
        for i in input:
            hasInput = True

            try:
                for t, c in baked:
                    if i.type == t:
                        yield from c().walk(i)
                        raise StopIteration
            except StopIteration:
                continue

            print("The following types have walkers:")
            print("\t%-20s %-20s" % ("WALKER", "TYPE"))
            for t, c in baked:
                print("\t%-20s %-20s" % (c().cmdName, t))
            raise TypeError('no walker found for input of type {}'.format(
                i.type))
        # If we got no input and we're the last thing in the pipeline, we're
        # probably the first thing in the pipeline. Print out the available
        # walkers.
        if not hasInput and self.islast:
            print("The following types have walkers:")
            print("\t%-20s %-20s" % ("WALKER", "TYPE"))
            for t, c in baked:
                print("\t%-20s %-20s" % (c().cmdName, t))
