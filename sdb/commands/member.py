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

# pylint: disable=missing-docstring

from typing import Iterable

import drgn
import sdb


class Member(sdb.Command):
    """
    This is an example help message
    """

    cmdName = "member"

    def __init__(self, prog: drgn.Program, args: str = "") -> None:
        super().__init__(prog, args)
        self.args = args

    def call(self, objs: Iterable[drgn.Object]) -> Iterable[drgn.Object]:
        members = self.args.split()
        for obj in objs:
            ret_object = obj
            if members:
                for i in members:
                    ret_object = ret_object.member_(i)
            yield ret_object
