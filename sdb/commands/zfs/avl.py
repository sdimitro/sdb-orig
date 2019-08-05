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


class Avl(sdb.Walker):
    """ walk avl tree """

    cmdName = "avl"
    inputType = "avl_tree_t *"

    def __init__(self, prog: drgn.Program, args: str = "") -> None:
        super().__init__(prog, args)

    def walk(self, input: drgn.Object) -> Iterable[drgn.Object]:
        offset = int(input.avl_offset)
        root = input.avl_root
        yield from self.helper(root, offset)

    def helper(self, node: drgn.Object, offset: int) -> Iterable[drgn.Object]:
        if node == drgn.NULL(self.prog, node.type_):
            return

        lchild = node.avl_child[0]
        yield from self.helper(lchild, offset)

        obj = drgn.Object(self.prog, type="void *", value=int(node) - offset)
        yield obj

        rchild = node.avl_child[1]
        yield from self.helper(rchild, offset)
