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

import inspect
import shlex
import subprocess
import sys
import traceback
from typing import Dict, Iterable, List, Optional, Type, Union

import drgn


class Command:
    """
    This is the superclass of all SDB command classes.

    This class intends to be the superclass of all other SDB command
    classes, and is responsible for implementing all the logic that is
    required to integrate the command with the SDB REPL.
    """

    allCommands: Dict[str, Type["Command"]] = {}

    inputType: Optional[str] = None

    # Subclasses should fill in this attribute if they want to be
    # registered as "real" gdb commands.  Typically all concrete
    # subclasses would do this
    cmdName: Optional[Union[List[str], str]] = None

    # pylint: disable=unused-argument
    def __init__(self, prog: drgn.Program, args: str = "") -> None:
        self.prog = prog
        self.islast = False
        self.ispipeable = False

        if inspect.signature(
                self.call).return_annotation == Iterable[drgn.Object]:
            self.ispipeable = True

    # When a subclass is created, if it has a 'cmdName' property, then
    # register it with gdb
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.cmdName:
            if isinstance(cls.cmdName, str):
                Command.register_command(cls.cmdName, cls)
            else:
                try:
                    for cname in cls.cmdName:
                        Command.register_command(cname, cls)
                except TypeError as err:
                    print("Invalid cmdName type in {}".format(cls))
                    raise err

    @staticmethod
    def register_command(name: str, cls: Type["Command"]) -> None:
        Command.allCommands[name] = cls

    # pylint: disable=too-many-locals
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-statements
    @staticmethod
    def invoke(prog: drgn.Program, argstr: str) -> None:
        shell_cmd = None
        # Parse the argument string. Each pipeline stage is delimited by
        # a pipe character "|". If there is a "!" character detected, then
        # pipe all the remaining outout into a subshell.
        lexer = shlex.shlex(argstr, posix=False, punctuation_chars="|!")
        lexer.wordchars += "();<>&[]"
        all_tokens = list(lexer)
        pipe_stages = []
        tokens: List[str] = []
        for num, token in enumerate(all_tokens):
            if token == "|":
                pipe_stages.append(" ".join(tokens))
                tokens = []
            elif token == "!":
                pipe_stages.append(" ".join(tokens))
                if any(t == "!" for t in all_tokens[num + 1:]):
                    print("Multiple ! not supported")
                    return
                shell_cmd = " ".join(all_tokens[num + 1:])
                break
            else:
                tokens.append(token)
        else:
            # We didn't find a !, so all remaining tokens are part of
            # the last pipe
            pipe_stages.append(" ".join(tokens))

        # Build the pipeline by constructing each of the commands we want to
        # use and building a list of them.
        pipeline = []
        for stage in pipe_stages:
            (cmdname, _, args) = stage.strip().partition(" ")
            try:
                if args:
                    pipeline.append(Command.allCommands[cmdname](prog, args))
                else:
                    pipeline.append(Command.allCommands[cmdname](prog))
            except KeyError:
                print("sdb: cannot recognize command: {}".format(cmdname))
                return

        pipeline[-1].set_islast()

        # If we have a !, redirect stdout to a shell process. This avoids
        # having to have a custom printing function that we pass around and
        # use everywhere. We'll fix stdout to point back to the normal stdout
        # at the end.
        if shell_cmd is not None:
            shell_proc = subprocess.Popen(shell_cmd,
                                          shell=True,
                                          stdin=subprocess.PIPE,
                                          encoding="utf-8")
            old_stdout = sys.stdout
            sys.stdout = shell_proc.stdin  # type: ignore

        try:
            if pipeline[-1].ispipeable:
                for obj in Command.execute_pipeline(prog, [], pipeline):
                    print(obj)
            else:
                Command.execute_pipeline_term(prog, [], pipeline)

            if shell_cmd is not None:
                shell_proc.stdin.flush()
                shell_proc.stdin.close()

        except BrokenPipeError:
            pass
        except Exception as err:  # pylint: disable=broad-except
            traceback.print_exc()
            print(err)
            return
        finally:
            if shell_cmd is not None:
                sys.stdout = old_stdout
                shell_proc.wait()

    # Run the pipeline, and yield the output. This function recurses
    # through the pipeline, providing each stage with the earlier stage's
    # outputs as input.
    @staticmethod
    def execute_pipeline(prog: drgn.Program, first_input: Iterable[drgn.Object],
                         args: List["Command"]) -> Iterable[drgn.Object]:
        if len(args) == 1:
            this_input = first_input
        else:
            this_input = Command.execute_pipeline(prog, first_input, args[:-1])

        yield from args[-1].call(this_input)

    # Run a pipeline that ends in a non-pipeable command. This function is
    # very similar to execute_pipeline, but it doesn't yield any results.
    @staticmethod
    def execute_pipeline_term(prog: drgn.Program,
                              first_input: Iterable[drgn.Object],
                              args: List["Command"]) -> None:
        if len(args) == 1:
            this_input = first_input
        else:
            this_input = Command.execute_pipeline(prog, first_input, args[:-1])

        args[-1].call(this_input)

    def call(self, objs: Iterable[drgn.Object]) -> Iterable[drgn.Object]:
        raise NotImplementedError

    def set_islast(self) -> None:
        self.islast = True
