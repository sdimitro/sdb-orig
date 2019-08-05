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

def is_hex(s: str) -> bool:
    try:
        int(s, 16)
        return True
    except ValueError:
        return False


def resolve_for_address(prog: drgn.Program, arg: str) -> drgn.Object:
    if is_hex(arg):
        return drgn.Object(prog, "void *", value=int(arg, 16))
    else:
        return prog[arg].address_of_()


class Address(sdb.Command):
    cmdName = ["address", "addr"]

    def __init__(self, prog: drgn.Program, args: str = "") -> None:
        super().__init__(prog, args)
        self.args = args

    def call(self, input: Iterable[drgn.Object]) -> Iterable[drgn.Object]:
        if len(self.args) > 0:
            for arg in self.args.split():
                yield resolve_for_address(self.prog, arg)
        else:
            for i in input:
                assert i.address_of_() is not None
                yield i.address_of_()
