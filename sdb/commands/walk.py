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

from typing import Dict, Iterable, Type

import drgn
import sdb


# A convenience command that will automatically dispatch to the appropriate
# walker based on the type of the input data.
class Walk(sdb.Command):
    cmdName = "walk"

    def __init__(self, prog: drgn.Program, args: str = "") -> None:
        super().__init__(prog, args)
        self.args = args

    def call(self, input: Iterable[drgn.Object]) -> Iterable[drgn.Object]:
        baked = [
            (self.prog.type(k), c) for k, c in sdb.Walker.allWalkers.items()
        ]
        hasInput = False
        for i in input:
            hasInput = True

            try:
                for t, c in baked:
                    if i.type_ == t:
                        yield from c(self.prog).walk(i)
                        raise StopIteration
            except StopIteration:
                continue

            print("The following types have walkers:")
            print("\t%-20s %-20s" % ("WALKER", "TYPE"))
            for t, c in baked:
                print("\t%-20s %-20s" % (c(self.prog).cmdName, t))
            raise TypeError("no walker found for input of type {}".format(
                i.type_))
        # If we got no input and we're the last thing in the pipeline, we're
        # probably the first thing in the pipeline. Print out the available
        # walkers.
        if not hasInput and self.islast:
            print("The following types have walkers:")
            print("\t%-20s %-20s" % ("WALKER", "TYPE"))
            for t, c in baked:
                print("\t%-20s %-20s" % (c(self.prog).cmdName, t))
