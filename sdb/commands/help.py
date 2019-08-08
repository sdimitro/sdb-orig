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


class Help(sdb.Command):
    """
    syntax: help <command> [<command> ...]

    Prints the help message of the command(s) specified.
    """

    cmdName = "help"

    def __init__(self, prog: drgn.Program, args: str = "") -> None:
        super().__init__(prog, args)
        self.args = args

    def call(self, objs: Iterable[drgn.Object]) -> None:
        if not self.args:
            print("syntax: help <command> [<command> ...]")
            return
        for cmd in self.args.split():
            if cmd in sdb.Command.allCommands:
                print(cmd)
                if sdb.Command.allCommands[cmd].__doc__ is None:
                    print("\n    <undocumented>\n")
                    return
                print(sdb.Command.allCommands[cmd].__doc__)
            else:
                print("command " + cmd + " doesn't exist")
