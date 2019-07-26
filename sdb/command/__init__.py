# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import argparse
import drgn
import inspect
import os
import subprocess
import sys
import shlex
import traceback
from typing import Iterable, Dict, List, Type, Union, Optional
from typing import TypeVar, Callable

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
                if args:
                    pipeline.append(allSDBCommands[cmdname](prog, args))
                else:
                    pipeline.append(allSDBCommands[cmdname](prog))
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
                SDBCommand.executePipelineTerm(prog, [], pipeline)
            else:
                for o in SDBCommand.executePipeline(prog, [], pipeline):
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
    def executePipeline(prog : drgn.Program, first_input : Iterable[drgn.Object], args : List["SDBCommand"]) -> Iterable[drgn.Object]:
        # if this stage wants its input in a certain type, insert a
        # "coerce" stage before it
        if args[-1].inputType is not None:
            args.insert(-1, Coerce(prog, args[-1].inputType, auxError='for "{}" command'.format(args[-1].cmdName)))
        if len(args) == 1:
            this_input = first_input
        else:
            this_input = SDBCommand.executePipeline(prog, first_input, args[:-1])
        yield from args[-1].call(this_input)

    # Run a pipeline that ends in a non-pipeable command. This function is
    # very similar to executePipeline, but it doesn't yield any results.
    @staticmethod
    def executePipelineTerm(prog : drgn.Program, first_input : Iterable[drgn.Object], args : List["SDBCommand"]) -> None:
        # if the last stage wants its input in a certain type, insert a
        # "coerce" stage before it
        assert not isinstance(args[-1], PipeableCommand)
        if args[-1].inputType is not None:
            args.insert(-1, Coerce(prog, args[-1].inputType, auxError='for "{}" command'.format(args[-1].cmdName)))
        if len(args) == 1:
            this_input = first_input
        else:
            this_input = SDBCommand.executePipeline(prog, first_input, args[:-1])
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

#
# A pipe command that massages its input types into the a different type. This
# usually involves stripping typedefs or qualifiers, adding pointers to go
# from a struct to a struct *, or casting an int or void * to the appropriate
# pointer type.
#
class Coerce(PipeableCommand):
    cmdName = 'coerce'
    def __init__(self, prog : drgn.Program, args : str = "void *", auxError : str = '')  -> None:
        super().__init__(prog, args)
        self.auxError = auxError
        self.type = self.prog.type(args)
        if self.type.kind is not drgn.TypeKind.POINTER:
            raise TypeError('can only coerce to pointer types, not {}'.format(self.type))

    def coerce(self, obj : drgn.Object) -> drgn.Object:
        # same type is fine
        if obj.type_ == self.type:
            return obj

        # "void *" can be coerced to any pointer type
        if obj.type_.kind is drgn.TypeKind.POINTER and obj.type_.primitive is drgn.PrimitiveType.C_VOID:
            return drgn.cast(self.type, obj)

        # integers can be coerced to any pointer typo
        if obj.type_.TypeKind is drgn.TypeKind.INT:
            return drgn.cast(self.type, obj)

        # XXX: Comment out for now, not sure how to port to drgn
        ## "type" can be coerced to "type *"
        #if obj.address is not None and obj.address.type == self.type:
        #    return obj.address.cast(self.type)

        raise TypeError("can not coerce {} to {} {}".format(obj.type_, self.type, self.auxError))

    def call(self, input : Iterable[drgn.Object]) -> Iterable[drgn.Object]:
        for i in input:
            yield self.coerce(i)

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

# A convenience command that will automatically dispatch to the appropriate
# walker based on the type of the input data.
class Walk(PipeableCommand):
    cmdName = 'walk'
    def __init__(self, prog : drgn.Program, args : str = '') -> None:
        super().__init__(prog, args)
        self.args = args

    def call(self, input : Iterable[drgn.Object]) -> Iterable[drgn.Object]:
        baked = [ (self.prog.type(k), c) for k, c in Walker.allWalkers.items() ]
        hasInput = False
        for i in input:
            hasInput = True

            try:
                for t, c in baked:
                    if i.type_ == t:
                        yield from c(self.prog).walk(i)
                        raise StopIteration
            except StopIteration:
                continue

            print("The following types have walkers:")
            print("\t%-20s %-20s" % ("WALKER", "TYPE"))
            for t, c in baked:
                print("\t%-20s %-20s" % (c(self.prog).cmdName, t))
            raise TypeError('no walker found for input of type {}'.format(
                i.type_))
        # If we got no input and we're the last thing in the pipeline, we're
        # probably the first thing in the pipeline. Print out the available
        # walkers.
        if not hasInput and self.islast:
            print("The following types have walkers:")
            print("\t%-20s %-20s" % ("WALKER", "TYPE"))
            for t, c in baked:
                print("\t%-20s %-20s" % (c(self.prog).cmdName, t))

##############################################################################
# Ported from: crash/commands/zfs/list.py
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
            yield drgn.Object(self.prog, type='void *', value=int(node) - offset)
            node = node.next

##############################################################################
# Ported from: crash/commands/zfs/avl.py
##############################################################################

class Avl(Walker):
    """ walk avl tree """

    cmdName = 'avl'
    inputType = 'avl_tree_t *'
    def __init__(self, prog : drgn.Program, args : str = '') -> None:
        super().__init__(prog, args)

    def walk(self, input : drgn.Object) -> Iterable[drgn.Object]:
        offset = int(input.avl_offset)
        root = input.avl_root
        yield from self.helper(root, offset)

    def helper(self, node : drgn.Object, offset : int) -> Iterable[drgn.Object]:
        if node == drgn.NULL(self.prog, node.type_):
            return

        lchild = node.avl_child[0]
        yield from self.helper(lchild, offset)

        obj = drgn.Object(self.prog, type='void *', value=int(node) - offset)
        yield obj

        rchild = node.avl_child[1]
        yield from self.helper(rchild, offset)

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
# Ported from: crash/commands/locator.py
##############################################################################

#
# A Locator is a command that locates objects of a given type.  Subclasses
# declare that they produce a given outputType (the type being located), and
# they provide a method for each input type that they can search for objects
# of this type.  Additionally, many locators are also PrettyPrinters, and can
# pretty print the things they find. There is some logic here to support that
# workflow.
#
class Locator(PipeableCommand):
    outputType : str = ''

    def __init__(self, prog : drgn.Program, args : str = '') -> None:
        super().__init__(prog, args)
        # We unset the inputType here so that the pipeline doesn't add a
        # coerce before us and ruin our ability to dispatch based on multiple
        # input types. For pure locators, and inputType wouldn't be set, but
        # hybrid Locators and PrettyPrinters will set an inputType so that
        # PrettyPrint can dispatch to them. By unsetting the inputType in the
        # instance, after registration is complete, PrettyPrint continues to
        # work, and the pipeline logic doesn't see an inputType to coerce to.
        self.inputType = None

    # subclass may override this
    def noInput(self) -> Iterable[drgn.Object]:
        raise TypeError('command "{}" requires and input'.format(
            self.cmdName))

    # Dispatch to the appropriate instance function based on the type of the
    # input we receive.
    def caller(self, input : Iterable[drgn.Object]) -> Iterable[drgn.Object]:
        out_type = self.prog.type(self.outputType)
        hasInput = False
        for i in input:
            hasInput = True

            # try subclass-specified input types first, so that they can override any other behavior
            try:
                for (name, method) in inspect.getmembers(self, inspect.ismethod):
                    if not hasattr(method, 'input_typename_handled'):
                        continue

                    # Cache parsed type by setting an attribute on the
                    # function that this method is bound to (same place
                    # the input_typename_handled attribute is set).
                    # Unfortunately we can't do this in the decorator
                    # because the gdb types have not been set up yet.
                    if not hasattr(method, 'input_type_handled'):
                        method.__func__.input_type_handled = self.prog.type(method.input_typename_handled)

                    if i.type_ == method.input_type_handled:
                        yield from method(i)
                        raise StopIteration
            except StopIteration:
                continue

            # try passthrough of output type
            # note, this may also be handled by subclass-specified input types
            if i.type_ == out_type:
                yield i
                continue

            # try walkers
            try:
                for o in Walk().call([i]):
                    yield drgn.cast(out_type, o)
                continue
            except TypeError:
                pass

            # error
            raise TypeError('command "{}" does not handle input of type {}'.format(
                self.cmdName,
                i.type_))
        if not hasInput:
            yield from self.noInput()

    def call(self, input : Iterable[drgn.Object]) -> Iterable[drgn.Object]:
        # If this is a hybrid locator/pretty printer, this is where that is leveraged.
        if self.islast and isinstance(self, PrettyPrinter):
            self.pretty_print(self.caller(input))
        else:
            yield from self.caller(input)

T = TypeVar('T', bound=Locator)
IH = Callable[[T, drgn.Object], Iterable[drgn.Object]]

def InputHandler(typename : str) -> Callable[[IH[T]], IH[T]]:
    def decorator(func : IH[T]) -> IH[T]:
        func.input_typename_handled = typename #type: ignore
        return func
    return decorator

##############################################################################
# Ported from: crash/commands/pretty_printer.py
##############################################################################

#
# Commands that are designed to format a specific type of data.
#
class PrettyPrinter(SDBCommand):
    allPrinters : Dict[str, Type["PrettyPrinter"]] = {}
    def __init__(self, prog : drgn.Program, args : str = '') -> None:
        super().__init__(prog, args)

    # When a subclass is created, register it
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        assert cls.inputType is not None
        PrettyPrinter.allPrinters[cls.inputType] = cls

    def pretty_print(self, input : Iterable[drgn.Object]) -> None:
        raise NotImplementedError

    # Invoke the pretty_print function on each input, checking types as we go.
    def call(self, input : Iterable[drgn.Object]) -> Iterable[drgn.Object]:
        assert self.inputType is not None
        t = self.prog.type(self.inputType)
        for i in input:
            if i.type_ != t:
                raise TypeError('command "{}" does not handle input of type {}'.format(
                    self.cmdName,
                    i.type_))

            self.pretty_print([i])
        return []

class PrettyPrint(SDBCommand):
    cmdName = 'pp'
    def __init__(self, prog : drgn.Program, args : str = '') -> None:
        super().__init__(prog, args)

    def call(self, input : Iterable[drgn.Object]) -> None: # type: ignore
        baked = [ (self.prog.type(t), c) for t, c in PrettyPrinter.allPrinters.items() ]
        hasInput = False
        for i in input:
            hasInput = True

            try:
                for t, c in baked:
                    if i.type_ == t and hasattr(c, "pretty_print"):
                        c(self.prog).pretty_print([i])
                        raise StopIteration
            except StopIteration:
                continue

            # error
            raise TypeError('command "{}" does not handle input of type {}'.format(
                self.cmdName,
                i.type_))
        # If we got no input and we're the last thing in the pipeline, we're
        # probably the first thing in the pipeline. Print out the available
        # pretty-printers.
        if not hasInput and self.islast:
            print("The following types have pretty-printers:")
            print("\t%-20s %-20s" % ("PRINTER", "TYPE"))
            for t, c in baked:
                if hasattr(c, "pretty_print"):
                    print("\t%-20s %-20s" % (c().cmdName, t))

##############################################################################
# Ported from: crash/commands/zfs/spa.py
##############################################################################

class Spa(Locator, PrettyPrinter):
    cmdName = 'spa'
    inputType = 'spa_t *'
    outputType = 'spa_t *'

    def __init__(self, prog : drgn.Program, args : str = '') -> None:
        super().__init__(prog, args)
        try:
            parser = argparse.ArgumentParser(description = "spa command")
            parser.add_argument('-v', '--vdevs',action='store_true',
                    help='vdevs flag' )
            parser.add_argument('-m', '--metaslab',action='store_true',
                    help='metaslab flag' )
            parser.add_argument('-H', '--histogram',action='store_true',
                    help='histogram flag' )
            parser.add_argument('-w', '--weight',action='store_true',
                    help='weight flag' )
            parser.add_argument('poolnames', nargs='*')
            self.args = parser.parse_args(args.split())
            self.arg_string = ""
            if self.args.metaslab:
                self.arg_string += "-m "
            if self.args.histogram:
                self.arg_string += "-H "
            if self.args.weight:
                self.arg_string += "-w "
        except:
            pass

    def pretty_print(self, spas):
        print("{:14} {}".format("ADDR", "NAME"))
        print("%s" % ('-' * 60))
        for spa in spas:
            print("{:14} {}".format(hex(spa), spa.spa_name.string_().decode('utf-8')))
            if self.args.vdevs:
                vdevs = SDBCommand.executePipeline(self.prog,
                        [spa], [Vdev(self.prog)])
                Vdev(self.prog, self.arg_string).pretty_print(vdevs, 5)

    def noInput(self):
        input = SDBCommand.executePipeline(self.prog,
                [self.prog['spa_namespace_avl'].address_of_()],
                [Avl(self.prog), Cast(self.prog, 'spa_t *')])
        for spa in input:
            if self.args.poolnames and spa.spa_name.string_() not in self.args.poolnames:
                continue
            yield spa

##############################################################################
# Ported from: crash/commands/zfs/zfs_util.py
##############################################################################

def enum_lookup(prog, enum_type_name, value):
    """ return a string which is the short name of the enum value
    (truncating off the common prefix """
    fields = prog.type(enum_type_name).type.enumerators
    prefix = os.path.commonprefix([ f[0] for f in fields ])
    return fields[value][0][prefix.rfind('_')+1:]

def print_histogram(histogram, size, offset):
    max_data = 0
    maxidx = 0
    minidx = size - 1

    for i in range(0, size):
        if (histogram[i] > max_data):
            max_data = histogram[i]
        if (histogram[i] > 0 and i > maxidx):
            maxidx = i
        if (histogram[i] > 0 and i < minidx):
            minidx = i
    if (max_data < 40):
        max_data = 40

    for i in range(minidx, maxidx + 1):
        print("%3u: %6u %s" % (i + offset, histogram[i],
            '*' * int(histogram[i])))

def nicenum(num, suffix='B'):
    for unit in [ '', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if (num < 1024):
            return "{}{}{}".format(int(num), unit, suffix)
        num /= 1024
    return "{}{}{}".format(int(num), "Y", suffix)

##############################################################################
# Ported from: crash/commands/zfs/vdev.py
##############################################################################

class Vdev(Locator, PrettyPrinter):
    cmdName = 'vdev'
    inputType = 'vdev_t *'
    outputType = 'vdev_t *'

    def __init__(self, prog : drgn.Program, args : str = '') -> None:
        super().__init__(prog, args)

        # XXX add flag for "direct children (from vdev) only"?
        # XXX add flag for "top level vdevs (from spa) only"?
        try:
            parser = argparse.ArgumentParser(description = "vdev command")
            parser.add_argument('-m', '--metaslab',action='store_true',
                    default=False, help='metaslab flag' )
            parser.add_argument('-H', '--histogram',action='store_true',
                    default=False, help='histogram flag' )
            parser.add_argument('-w', '--weight',action='store_true',
                    default=False, help='weight flag' )
            parser.add_argument('vdev_ids', nargs='*', type=int)
            self.args = parser.parse_args(args.split())
            self.arg_string = ""
            if self.args.histogram:
                self.arg_string += "-H "
            if self.args.weight:
                self.arg_string += "-w "
        except:
            pass

    # arg is iterable of gdb.Value of type vdev_t*
    def pretty_print(self, vdevs, indent=0):
        print("".ljust(indent), "ADDR".ljust(18), "STATE".ljust(7),
                "AUX".ljust(4), "DESCRIPTION")
        print("".ljust(indent), "-" * 60)

        for vdev in vdevs:
            level = 0
            pvd = vdev.vdev_parent
            while pvd:
                level += 2
                pvd = pvd.vdev_parent

            if int(vdev.vdev_path) != 0:
                print("".ljust(indent), hex(vdev).ljust(18),
                     enum_lookup(self.prog, 'vdev_state_t', vdev.vdev_state).ljust(7),
                     enum_lookup(self.prog, 'vdev_aux_t',
                        vdev.vdev_stat.vs_aux).ljust(4),
                     "".ljust(level),
                     vdev.vdev_path.string_().decode('utf-8'))

            else:
                print("".ljust(indent), hex(vdev).ljust(18),
                     enum_lookup(self.prog, 'vdev_state_t', vdev.vdev_state).ljust(7),
                     enum_lookup(self.prog, 'vdev_aux_t',
                        vdev.vdev_stat.vs_aux).ljust(4),
                     "".ljust(level),
                     vdev.vdev_ops.vdev_op_type.string_().decode('utf-8'))
            if self.args.metaslab:
                metaslabs = SDBCommand.executePipeline(self.prog, [vdev], [Metaslab(self.prog)])
                Metaslab(self.prog, self.arg_string).pretty_print(metaslabs, indent + 5)

    # arg is gdb.Value of type spa_t*
    # need to yield gdb.Value's of type vdev_t*
    @InputHandler('spa_t*')
    def from_spa(self, spa : drgn.Object) -> Iterable[drgn.Object]:
        if self.args.vdev_ids:
            # yield the requested top-level vdevs
            for id in self.args.vdev_ids:
                if id >= spa.spa_root_vdev.vdev_children:
                    raise TypeError('vdev id {} not valid; there are only {} vdevs in {}'.format(
                        id,
                        spa.spa_root_vdev.vdev_children,
                        spa.spa_name.string_().decode('utf-8')))
                yield spa.spa_root_vdev.vdev_child[id]
        else:
            yield from self.from_vdev(spa.spa_root_vdev)

    # arg is gdb.Value of type vdev_t*
    # need to yield gdb.Value's of type vdev_t*
    @InputHandler('vdev_t*')
    def from_vdev(self, vdev : drgn.Object) -> Iterable[drgn.Object]:
        if self.args.vdev_ids:
            raise TypeError('when providing a vdev, specific child vdevs can not be requested')
        yield vdev
        for cid in range(0, int(vdev.vdev_children)):
            cvd = vdev.vdev_child[cid]
            yield from self.from_vdev(cvd)

##############################################################################
# Ported from: crash/commands/zfs/zfs_init.py
##############################################################################

P2PHASE : Callable[[drgn.Object, int], drgn.Object]			= lambda x, align : ((x) & ((align) - 1))
BF64_DECODE : Callable[[drgn.Object, int, int], int]	= lambda x, low, len : int(P2PHASE(x >> low, 1 << len))
BF64_GET : Callable[[drgn.Object, int, int], int]		= lambda x, low, len : BF64_DECODE(x, low, len)

WEIGHT_IS_SPACEBASED = lambda weight : weight == 0 or BF64_GET(weight, 60, 1)
WEIGHT_GET_INDEX = lambda weight : BF64_GET((weight), 54, 6)
WEIGHT_GET_COUNT = lambda weight : BF64_GET((weight), 0, 54)

METASLAB_WEIGHT_PRIMARY = int(1 << 63)
METASLAB_WEIGHT_SECONDARY = int(1 << 62)
METASLAB_WEIGHT_CLAIM = int(1 << 61)
METASLAB_WEIGHT_TYPE = int(1 << 60)
METASLAB_ACTIVE_MASK = METASLAB_WEIGHT_PRIMARY | METASLAB_WEIGHT_SECONDARY  | METASLAB_WEIGHT_CLAIM

##############################################################################
# Ported from: crash/commands/zfs/metaslab.py
##############################################################################

class Metaslab(Locator, PrettyPrinter):
    cmdName = 'metaslab'
    inputType = 'metaslab_t *'
    outputType = 'metaslab_t *'

    def __init__(self, prog : drgn.Program, args : str = '') -> None:
        super().__init__(prog, args)

        try:
            parser = argparse.ArgumentParser(prog='metaslab')
            parser.add_argument('-H', '--histogram',action='store_true',
                    default=False, help='histogram flag' )
            parser.add_argument('-w', '--weight',action='store_true',
                    default=False, help='weight flag' )
            parser.add_argument('metaslab_ids', nargs='*', type=int)
            self.args = parser.parse_args(args.split())
        except:
            pass

    def metaslab_weight_print(prog : drgn.Program, msp, print_header, indent):
        if print_header:
            print("".ljust(indent), "ID".rjust(3), "ACTIVE".ljust(6),
                    "ALGORITHM".rjust(9), "FRAG".rjust(4),
                    "ALLOC".rjust(10), "MAXSZ".rjust(12),
                    "WEIGHT".rjust(12))
            print("".ljust(indent), "-" * 65)
        weight = int(msp.ms_weight)
        if weight & METASLAB_WEIGHT_PRIMARY:
            w = "P"
        elif weight & METASLAB_WEIGHT_SECONDARY:
            w = "S"
        elif weight & METASLAB_WEIGHT_CLAIM:
            w = "C"
        else:
            w = "-"

        if WEIGHT_IS_SPACEBASED(weight):
            algorithm = "SPACE"
        else:
            algorithm = "SEGMENT"

        print("".ljust(indent), str(int(msp.ms_id)).rjust(3), w.rjust(4),
                "L" if msp.ms_loaded else " ", algorithm.rjust(8), end='')
        if msp.ms_fragmentation == -1:
            print('-'.rjust(6), end='')
        else:
            print((str(msp.ms_fragmentation) + "%").rjust(5), end='')
        print(str(str(int(msp.ms_allocated_space) >> 20) + "M").rjust(7),
            ("({0:.1f}%)".format(int(msp.ms_allocated_space) * 100 / int(msp.ms_size)).rjust(7)),
            nicenum(msp.ms_max_size).rjust(10), end="")

        if (WEIGHT_IS_SPACEBASED(weight)):
            print("", nicenum(weight & ~(METASLAB_ACTIVE_MASK |
                METASLAB_WEIGHT_TYPE)).rjust(12))
        else:
            count = str(WEIGHT_GET_COUNT(weight))
            size = nicenum(1 << WEIGHT_GET_INDEX(weight))
            print("", (count + ' x ' + size).rjust(12))


    def print_metaslab(prog : drgn.Program, msp, print_header, indent):
        sm = msp.ms_sm

        if print_header:
            print("".ljust(indent), "ADDR".ljust(18), "ID".rjust(4),
                    "OFFSET".rjust(16), "FREE".rjust(8), "FRAG".rjust(5),
                    "UCMU".rjust(8))
            print("".ljust(indent), '-' * 65)

        free = msp.ms_size
        if sm != drgn.NULL(prog, sm.type_):
            free -= sm.sm_phys.smp_alloc

        ufrees = msp.ms_unflushed_frees.rt_space
        uallocs = msp.ms_unflushed_allocs.rt_space
        free = free + ufrees - uallocs

        uchanges_free_mem = msp.ms_unflushed_frees.rt_root.avl_numnodes
        uchanges_free_mem *= prog.type('range_seg_t').type.size
        uchanges_alloc_mem = msp.ms_unflushed_allocs.rt_root.avl_numnodes
        uchanges_alloc_mem *= prog.type('range_seg_t').type.size
        uchanges_mem = uchanges_free_mem + uchanges_alloc_mem

        print("".ljust(indent), hex(msp).ljust(16),
                str(int(msp.ms_id)).rjust(4),
                hex(msp.ms_start).rjust(16),
                nicenum(free).rjust(8), end='')
        if msp.ms_fragmentation == -1:
            print('-'.rjust(6), end='')
        else:
            print((str(msp.ms_fragmentation) + "%").rjust(6), end='')
        print(nicenum(uchanges_mem).rjust(9))


    def pretty_print(self, metaslabs, indent=0):
        first_time = True
        for msp in metaslabs:
            if not self.args.histogram and not self.args.weight:
                Metaslab.print_metaslab(self.prog, msp, first_time, indent)
            if self.args.histogram:
                sm = msp.ms_sm
                if sm != drgn.NULL(self.prog, sm.type_):
                    histogram = sm.sm_phys.smp_histogram
                    print_histogram(histogram, 32, sm.sm_shift)
            if self.args.weight:
                Metaslab.metaslab_weight_print(self.prog, msp, first_time, indent)
            first_time = False


# XXX - removed because of circular dependencies when importing Vdev class
#
#    def metaslab_from_spa(self, spa):
#        vdevs = SDBCommand.executePipeline([spa], [Vdev()])
#        for vd in vdevs:
#            yield from self.metaslab_from_vdev(vd)

    @InputHandler('vdev_t*')
    def from_vdev(self, vdev : drgn.Object) -> Iterable[drgn.Object]:
        if self.args.metaslab_ids:
            # yield the requested metaslabs
            for id in self.args.metaslab_ids:
                if id >= vdev.vdev_ms_count:
                    raise TypeError('metaslab id {} not valid; there are only {} metaslabs in vdev id {}'.format(
                        id,
                        vdev.vdev_ms_count,
                        vdev.vdev_id))
                yield vdev.vdev_ms[id]
        else:
            for m in range(0, int(vdev.vdev_ms_count)):
                msp = vdev.vdev_ms[m]
                yield msp

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
        for node in SDBCommand.executePipeline(self.prog, [list_addr], [List(self.prog), Cast(self.prog, 'zfs_dbgmsg_t *')]):
            ZfsDbgmsg.print_msg(node, self.verbosity >= 1, self.verbosity >= 2)

##############################################################################
# Experimental
##############################################################################

class Echo(PipeableCommand):
    cmdName = ['echo', 'cc']
    def __init__(self, prog : drgn.Program, args : str = '') -> None:
        super().__init__(prog, args)
        self.args = args

    def call(self, input : Iterable[drgn.Object]) -> Iterable[drgn.Object]:
        for arg in self.args.split():
            yield drgn.Object(self.prog, 'void *', value=int(arg, 0))
        for o in input:
            yield o

def is_hex(s : str) -> bool:
    try:
        int(s, 16)
        return True
    except ValueError:
        return False

def resolve_for_address(prog : drgn.Program, arg : str) -> drgn.Object:
    if is_hex(arg):
        return drgn.Object(prog, 'void *', value=int(arg, 16))
    else:
        return prog[arg].address_of_()

class Address(PipeableCommand):
    cmdName = ['address', 'addr']
    def __init__(self, prog : drgn.Program, args : str = '') -> None:
        super().__init__(prog, args)
        self.args = args

    def call(self, input : Iterable[drgn.Object]) -> Iterable[drgn.Object]:
        if len(self.args) > 0:
            for arg in self.args.split():
                yield resolve_for_address(self.prog, arg)
        else:
            for i in input:
                assert i.address_of_() is not None
                yield i.address_of_()

class Member(PipeableCommand):
    """
    This is an example help message
    """
    cmdName = 'member'
    def __init__(self, prog : drgn.Program, args : str = '') -> None:
        super().__init__(prog, args)
        self.args = args

    def call(self, input : Iterable[drgn.Object]) -> Iterable[drgn.Object]:
        members = self.args.split()
        for o in input:
            retObject = o
            if len(members) != 0:
                for m in members:
                    retObject = retObject.member_(m)
            yield retObject

class Help(SDBCommand):
    cmdName = "help"

    def __init__(self, prog : drgn.Program, args : str = '') -> None:
        super().__init__(prog, args)
        self.args = args

    def call(self, input : Iterable[drgn.Object]) -> None:
        if len(self.args) == 0:
            print('syntax: help <command>')
            return
        for cmd in self.args.split():
            if cmd in allSDBCommands:
                print(cmd)
                print(allSDBCommands[cmd].__doc__)
            else:
                print("command " + cmd + " doesn't exist")

# TODO: Proper error-handling everywhere
