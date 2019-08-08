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

import datetime
import getopt
from typing import Iterable

import drgn
import sdb
from sdb.commands.cast import Cast
from sdb.commands.zfs.list import List


class ZfsDbgmsg(sdb.Locator, sdb.PrettyPrinter):
    cmdName = "zfs_dbgmsg"
    input_type = "zfs_dbgmsg_t *"
    outputType = "zfs_dbgmsg_t *"

    def __init__(self, prog: drgn.Program, args: str = "") -> None:
        super().__init__(prog, args)
        self.verbosity = 0

        optlist, args = getopt.getopt(args.split(), "v")
        if args:
            print("Improper arguments to ::zfs_dbgmsg: {}\n".format(args))
            return
        for (opt, arg) in optlist:
            if opt != "-v":
                print("Improper flag to ::zfs_dbgmsg: {}\n".format(opt))
                return
            if arg != "":
                print("Improper value to ::zfs_dbgmsg: {}\n".format(arg))
                return
            self.verbosity += 1

    # obj is a zfs_dbgmsg_t*
    @staticmethod
    def print_msg(obj: drgn.Object, timestamp: bool = False,
                  addr: bool = False) -> None:
        if addr:
            print("{} ".format(hex(obj)), end="")  # type: ignore
        if timestamp:
            timestamp = datetime.datetime.fromtimestamp(int(obj.zdm_timestamp))
            print("{}: ".format(timestamp.strftime("%Y-%m-%dT%H:%M:%S")),
                  end="")

        print(drgn.cast("char *", obj.zdm_msg).string_().decode("utf-8"))

    def pretty_print(self, objs: Iterable[drgn.Object]) -> None:
        for obj in objs:
            ZfsDbgmsg.print_msg(obj, self.verbosity >= 1, self.verbosity >= 2)

    def no_input(self) -> Iterable[drgn.Object]:
        proc_list = self.prog["zfs_dbgmsgs"].pl_list
        list_addr = proc_list.address_of_()

        for obj in sdb.Command.execute_pipeline(
                self.prog, [list_addr],
                [List(self.prog), Cast(self.prog, "zfs_dbgmsg_t *")]):
            yield obj
