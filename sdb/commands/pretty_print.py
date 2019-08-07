#
# Copyright 2019 Delphix
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from typing import Iterable

import drgn
import sdb


class PrettyPrint(sdb.Command):
    cmdName = ["pretty_print", "pp"]

    def __init__(self, prog: drgn.Program, args: str = "") -> None:
        super().__init__(prog, args)

    def call(self, input: Iterable[drgn.Object]) -> None:  # type: ignore
        baked = [(self.prog.type(t), c)
                 for t, c in sdb.PrettyPrinter.allPrinters.items()]
        hasInput = False
        for i in input:
            hasInput = True

            try:
                for t, c in baked:
                    if i.type_ == t and hasattr(c, "pretty_print"):
                        c(self.prog).pretty_print([i])
                        raise StopIteration
            except StopIteration:
                continue

            # error
            raise TypeError(
                'command "{}" does not handle input of type {}'.format(
                    self.cmdName, i.type_))
        # If we got no input and we're the last thing in the pipeline, we're
        # probably the first thing in the pipeline. Print out the available
        # pretty-printers.
        if not hasInput and self.islast:
            print("The following types have pretty-printers:")
            print("\t%-20s %-20s" % ("PRINTER", "TYPE"))
            for t, c in baked:
                if hasattr(c, "pretty_print"):
                    print("\t%-20s %-20s" % (c(self.prog).cmdName, t))
