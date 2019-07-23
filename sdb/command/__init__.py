# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import drgn
import subprocess
import sys
import shlex
import traceback
from typing import Iterable, Dict, List, Type, Union, Optional

allSDBCommands = {}

#
# This class is the superclass of all commands intended for use with SDB. The
# distinguishing feature of SDB commands is that they take an input to their
# `call` method.
#
class SDBCommand(object):
    inputType : Optional[str] = None

    # Subclasses should fill in this attribute if they want to be
    # registered as "real" gdb commands.  Typically all concrete
    # subclasses would do this
    cmdName : Optional[Union[List[str],str]] = None

    def __init__(self, prog : drgn.Program, args : str = '') -> None:
        self.prog = prog
        self.islast = False

    # When a subclass is created, if it has a 'cmdName' property, then
    # register it with gdb
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.cmdName:
            if isinstance(cls.cmdName, str):
                SDBCommand.registerSDBCommand(cls.cmdName, cls)
            else:
                try:
                    for cname in cls.cmdName:
                        SDBCommand.registerSDBCommand(cname, cls)
                except TypeError as e:
                    print('Invalid cmdName type in {}'.format(cls))
                    raise e

    @staticmethod
    def registerSDBCommand(name : str, c : Type["SDBCommand"]) -> None:
        allSDBCommands[name] = c

    @staticmethod
    def invoke(prog : drgn.Program, argstr : str) -> None:
        shell_cmd = None
        # Parse the argument string. Each pipeline stage is delimited by
        # a pipe character "|". If there is a "!" character detected, then
        # pipe all the remaining outout into a subshell.
        lexer = shlex.shlex(argstr, posix=False, punctuation_chars="|!")
        lexer.wordchars += '();<>&[]'
        all_tokens = list(lexer)
        pipe_stages = []
        tokens : List[str] = []
        for n, token in enumerate(all_tokens):
            if token == '|':
                pipe_stages.append(' '.join(tokens))
                tokens = []
            elif token == '!':
                pipe_stages.append(' '.join(tokens))
                if any(t == '!' for t in all_tokens[n + 1:]):
                    print("Multiple ! not supported")
                    return
                shell_cmd = ' '.join(all_tokens[n + 1:])
                break
            else:
                tokens.append(token)
        else:
            # We didn't find a !, so all remaining tokens are part of
            # the last pipe
            pipe_stages.append(' '.join(tokens))

        # Build the pipeline by constructing each of the commands we want to
        # use and building a list of them.
        pipeline = []
        for stage in pipe_stages:
            (cmdname, space, args) = stage.strip().partition(' ')
            try:
                pipeline.append(allSDBCommands[cmdname](prog, args))
            except KeyError as e:
                print('No command named "{}" found'.format(cmdname))
                return

        pipeline[-1].setIsLast()

        # If we have a !, redirect stdout to a shell process. This avoids
        # having to have a custom printing function that we pass around and
        # use everywhere. We'll fix stdout to point back to the normal stdout
        # at the end.
        if shell_cmd is not None:
            shell_proc = subprocess.Popen(shell_cmd, shell=True, stdin=subprocess.PIPE, encoding='utf-8')
            old_stdout = sys.stdout
            sys.stdout = shell_proc.stdin # type: ignore

        try:
            # If the last step in the pipeline isn't a PipeableCommand, it's
            # not going to yield anything. We call executePipelineTerm in that
            # case so that we don't run into an issue where the pipeline
            # doesn't pull properly because of generator quirks.
            if not isinstance(pipeline[-1], PipeableCommand):
                SDBCommand.executePipelineTerm([], pipeline)
            else:
                for o in SDBCommand.executePipeline([], pipeline):
                    print(o)

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

    # Run the pipeline, and yield the output. This function recurses through
    # the pipeline, providing each stage with the earlier stage's outputs as
    # input.
    @staticmethod
    def executePipeline(first_input : Iterable[drgn.Object], args : List["SDBCommand"]) -> Iterable[drgn.Object]:
        if len(args) == 1:
            this_input = first_input
        else:
            this_input = SDBCommand.executePipeline(first_input, args[:-1])
        yield from args[-1].call(this_input)

    # Run a pipeline that ends in a non-pipeable command. This function is
    # very similar to executePipeline, but it doesn't yield any results.
    @staticmethod
    def executePipelineTerm(first_input : Iterable[drgn.Object], args : List["SDBCommand"]) -> None:
        assert not isinstance(args[-1], PipeableCommand)
        if len(args) == 1:
            this_input = first_input
        else:
            this_input = SDBCommand.executePipeline(first_input, args[:-1])
        args[-1].call(this_input)

    # subclass must override this, typically with a generator, i.e. it must use `yield`
    def call(self, input : Iterable[drgn.Object]) -> Iterable[drgn.Object]:
        raise NotImplementedError

    # called if this is the last thing in the pipeline
    def setIsLast(self) -> None:
        self.islast = True

#
# Commands whose call function yields an iterable of some kind; usually a
# generator, for performance reasons.
#
class PipeableCommand(SDBCommand):
    def __init__(self, prog : drgn.Program, args : str = '') -> None:
        super().__init__(prog, args)
        rv = self.call([])
        assert (rv is not None and rv.__iter__ is not None), "{}.call() does not return an iterable".format(type(self).__name__)

##############################################################################
# Ported from: crash/commands/walk.py
##############################################################################

#
# Commands that are designed to iterate over data structures that contain
# arbitrary data types
#
class Walker(PipeableCommand):
    allWalkers : Dict[str, Type["Walker"]] = {}
    def __init__(self, prog : drgn.Program, args : str = '') -> None:
        super().__init__(prog, args)

    # When a subclass is created, register it
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        assert cls.inputType is not None
        Walker.allWalkers[cls.inputType] = cls

    def walk(self, input : drgn.Object) -> Iterable[drgn.Object]:
        raise NotImplementedError

    # Iterate over the inputs and call the walk command on each of them,
    # verifying the types as we go.
    def call(self, input : Iterable[drgn.Object]) -> Iterable[drgn.Object]:
        assert self.inputType is not None
        t = self.prog.type(self.inputType)
        for i in input:
            if i.type_ != t:
                raise TypeError('command "{}" does not handle input of type {}'.format(
                    self.cmdName,
                    i.type_))

            yield from self.walk(i)

##############################################################################
# Ported from:
##############################################################################

class List(Walker):
    cmdName = 'list'
    inputType = 'list_t *'
    def __init__(self, prog : drgn.Program, args : str = '') -> None:
        super().__init__(prog, args)

    def walk(self, input : drgn.Object) -> Iterable[drgn.Object]:
        offset = int(input.list_offset)
        first_node = input.list_head.address_of_()
        node = first_node.next
        while node != first_node:
            yield drgn.Object(self.prog, type='void *', address=node.address_of_() - offset)
            node = node.next

##############################################################################
# Ported from: crash/commands/cast.py
##############################################################################

class Cast(PipeableCommand):
    cmdName = 'cast'
    def __init__(self, prog : drgn.Program, args : str = '') -> None:
        super().__init__(prog, args)
        self.type = self.prog.type(args)

    def call(self, input : Iterable[drgn.Object]) -> Iterable[drgn.Object]:
        for obj in input:
            yield drgn.cast(self.type, obj)

##############################################################################
# Ported from: crash/commands/zfs/zfs_dbgmsg.py
##############################################################################

import datetime
import getopt

class ZfsDbgmsgArg():
    ts : bool = False
    addr : bool = False
    def __init__(self, ts : bool = False, addr : bool = False):
        self.ts = ts
        self.addr = addr

class ZfsDbgmsg(SDBCommand):
    cmdName = "zfs_dbgmsg"

    def __init__(self, prog : drgn.Program, args : str = '') -> None:
        super().__init__(prog, args)
        self.verbosity = 0

        optlist, args = getopt.getopt(args.split(), 'v')
        if len(args) != 0:
            print("Improper arguments to ::zfs_dbgmsg: {}\n".format(args))
            return
        for (opt, arg) in optlist:
            if opt != '-v':
                print ("Improper flag to ::zfs_dbgmsg: {}\n".format(opt))
                return
            elif arg != '':
                print ("Improper value to ::zfs_dbgmsg: {}\n".format(arg))
                return
            self.verbosity += 1

    #node is a zfs_dbgmsg_t*
    @staticmethod
    def print_msg(node : drgn.Object, ts : bool = False, addr : bool = False) -> None:
        if addr:
            print("{} ".format(hex(node)), end="") # type: ignore
        if ts:
            timestamp = datetime.datetime.fromtimestamp(int(node.zdm_timestamp))
            print("{}: ".format(timestamp.strftime('%Y-%m-%dT%H:%M:%S')), end="")

        print(drgn.cast('char *', node.zdm_msg).string_().decode('utf-8'))

    def call(self, input : Iterable[drgn.Object]) -> None:
        proc_list = self.prog['zfs_dbgmsgs'].pl_list
        list_addr = proc_list.address_of_()
        for node in SDBCommand.executePipeline([list_addr], [List(self.prog), Cast(self.prog, 'zfs_dbgmsg_t *')]):
            ZfsDbgmsg.print_msg(node, self.verbosity >= 1, self.verbosity >= 2)
