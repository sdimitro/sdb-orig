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

import argparse
from typing import Iterable

import drgn
import sdb


class LinuxHList(sdb.Walker):
    """ walk linux hlist_head """

    cmdName = "linux_hlist"
    input_type = "struct hlist_head *"

    def __init__(self, prog: drgn.Program, args: str = "") -> None:
        super().__init__(prog, args)
        parser = argparse.ArgumentParser(description="walk a linux hlist")
        parser.add_argument(
            "offset",
            default=0,
            type=int,
            nargs="?",
            help="offset of list_head in structure",
        )

        try:
            self.args = parser.parse_args(args.split())
        except SystemExit:
            pass

    def walk(self, input: drgn.Object) -> Iterable[drgn.Object]:
        node = input.first
        while node != 0:
            yield drgn.Object(self.prog,
                              type="void *",
                              value=(int(node) - self.args.offset))
            node = node.next
