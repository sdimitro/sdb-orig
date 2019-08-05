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

#
# A Walker is a command that is designed to iterate over data structures
# that contain arbitrary data types.
#

class Walker(sdb.Command):
    allWalkers: Dict[str, Type["Walker"]] = {}

    def __init__(self, prog: drgn.Program, args: str = "") -> None:
        super().__init__(prog, args)

    # When a subclass is created, register it
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        assert cls.inputType is not None
        Walker.allWalkers[cls.inputType] = cls

    def walk(self, input: drgn.Object) -> Iterable[drgn.Object]:
        raise NotImplementedError

    # Iterate over the inputs and call the walk command on each of them,
    # verifying the types as we go.
    def call(self, input: Iterable[drgn.Object]) -> Iterable[drgn.Object]:
        assert self.inputType is not None
        t = self.prog.type(self.inputType)
        for i in input:
            if i.type_ != t:
                raise TypeError(
                    'command "{}" does not handle input of type {}'.format(
                        self.cmdName, i.type_
                    )
                )

            yield from self.walk(i)
