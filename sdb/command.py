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

import inspect
import shlex
import subprocess
import sys
import traceback
from typing import Dict, Iterable, List, Optional, Type, Union

import drgn

#
# This class is the superclass of all commands intended for use with SDB. The
# distinguishing feature of SDB commands is that they take an input to their
# `call` method.
#


class Command(object):
    allCommands: Dict[str, Type["Command"]] = {}

    inputType: Optional[str] = None

    # Subclasses should fill in this attribute if they want to be
    # registered as "real" gdb commands.  Typically all concrete
    # subclasses would do this
    cmdName: Optional[Union[List[str], str]] = None

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
                Command.registerCommand(cls.cmdName, cls)
            else:
                try:
                    for cname in cls.cmdName:
                        Command.registerCommand(cname, cls)
                except TypeError as e:
                    print("Invalid cmdName type in {}".format(cls))
                    raise e

    @staticmethod
    def registerCommand(name: str, c: Type["Command"]) -> None:
        Command.allCommands[name] = c

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
        for n, token in enumerate(all_tokens):
            if token == "|":
                pipe_stages.append(" ".join(tokens))
                tokens = []
            elif token == "!":
                pipe_stages.append(" ".join(tokens))
                if any(t == "!" for t in all_tokens[n + 1:]):
                    print("Multiple ! not supported")
                    return
                shell_cmd = " ".join(all_tokens[n + 1:])
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
            (cmdname, space, args) = stage.strip().partition(" ")
            try:
                if args:
                    pipeline.append(Command.allCommands[cmdname](prog, args))
                else:
                    pipeline.append(Command.allCommands[cmdname](prog))
            except KeyError:
                print("sdb: cannot recognize command: {}".format(cmdname))
                return

        pipeline[-1].setIsLast()

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
                for o in Command.executePipeline(prog, [], pipeline):
                    print(o)
            else:
                Command.executePipelineTerm(prog, [], pipeline)

            if shell_cmd is not None:
                shell_proc.stdin.flush()
                shell_proc.stdin.close()

        except BrokenPipeError:
            pass
        except Exception as e:
            traceback.print_exc()
            print(e)
            return
        finally:
            if shell_cmd is not None:
                sys.stdout = old_stdout
                shell_proc.wait()

    # Run the pipeline, and yield the output. This function recurses
    # through the pipeline, providing each stage with the earlier stage's
    # outputs as input.
    @staticmethod
    def executePipeline(prog: drgn.Program, first_input: Iterable[drgn.Object],
                        args: List["Command"]) -> Iterable[drgn.Object]:
        if len(args) == 1:
            this_input = first_input
        else:
            this_input = Command.executePipeline(prog, first_input, args[:-1])
        yield from args[-1].call(this_input)

    # Run a pipeline that ends in a non-pipeable command. This function is
    # very similar to executePipeline, but it doesn't yield any results.
    @staticmethod
    def executePipelineTerm(prog: drgn.Program,
                            first_input: Iterable[drgn.Object],
                            args: List["Command"]) -> None:
        if len(args) == 1:
            this_input = first_input
        else:
            this_input = Command.executePipeline(prog, first_input, args[:-1])
        args[-1].call(this_input)

    # subclass must override this, typically with a generator, i.e. it must
    # use `yield`
    def call(self, input: Iterable[drgn.Object]) -> Iterable[drgn.Object]:
        raise NotImplementedError

    # called if this is the last thing in the pipeline
    def setIsLast(self) -> None:
        self.islast = True
