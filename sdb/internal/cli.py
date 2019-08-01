#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This file contains all the logic of the sdb "executable"
like the entry point, command line interface, etc...
"""

import argparse
import sys

import drgn
from sdb.command import allSDBCommands
from sdb.repl import REPL


def parse_arguments() -> argparse.Namespace:
    """
    Sets up argument parsing and does the first pass of validation
    of the command line input.
    """
    parser = argparse.ArgumentParser(
        prog="sdb", description="The Slick/Simple Debugger"
    )

    dump_group = parser.add_argument_group("core/crash dump analysis")
    dump_group.add_argument(
        "object",
        nargs="?",
        default="",
        help="a namelist like vmlinux or userland binary",
    )
    dump_group.add_argument(
        "core", nargs="?", default="", help="the core/crash dump to be debugged"
    )

    live_group = parser.add_argument_group(
        "live system analysis"
    ).add_mutually_exclusive_group()
    live_group.add_argument(
        "-k", "--kernel", action="store_true", help="debug the running kernel (default)"
    )
    live_group.add_argument(
        "-p",
        "--pid",
        metavar="PID",
        type=int,
        help="debug the running process of the specified PID",
    )

    dis_group = parser.add_argument_group("debug info and symbols")
    dis_group.add_argument(
        "-s",
        "--symbol-search",
        metavar="PATH",
        type=str,
        action="append",
        help="load debug info and symbols from the given directory or file;"
        + " this may option may be given more than once",
    )
    dis_group.add_argument(
        "-A",
        "--no-default-symbols",
        dest="default_symbols",
        action="store_false",
        help="don't load any debugging symbols that were not explicitly added with -d",
    )

    parser.add_argument(
        "-q", "--quiet", action="store_true", help="don't print non-fatal warnings"
    )
    args = parser.parse_args()

    #
    # If an 'object' (and maybe 'core') parameter has been specified
    # we are analyzing a core dump or a crash dump. With that in mind
    # it is harder to user argparse to make the above two mutually
    # exclusive with '-k' or '-p PID' which are for analyzing live
    # targets. As a result we enforce this mutual exclusions on our
    # own below. Unfortunately this is still not close to ideal as
    # the help message will show something like this:
    # ```
    # usage: sdb [-h] [-k | -p PID] [-d PATH] ... [object] [core]
    # ```
    # instead of:
    # ```
    # usage: sdb [-h] [-k | -p PID | object core] [-d PATH] ...
    # ```
    #
    if args.object and args.kernel:
        parser.error("cannot specify an object file while also specifying --kernel")
    if args.object and args.pid:
        parser.error("cannot specify an object file while also specifying --pid")

    #
    # We currently cannot handle object files without cores.
    #
    if args.object and not args.core:
        parser.error("raw object file target is not supported yet")
    return args


def setup_target(args: argparse.Namespace) -> drgn.Program:
    """
    Based on the validated input from the command line, setup the
    drgn.Program for our target and its metadata.
    """
    prog = drgn.Program()
    if args.core:
        prog.set_core_dump(args.core)

        #
        # This is currently a short-coming of drgn. Whenever we
        # open a crash/core dump we need to specify the vmlinux
        # or userland binary using the non-default debug info
        # load API.
        #
        prog.load_debug_info(args.object)
    elif args.pid:
        prog.set_pid(args.pid)
    else:
        prog.set_kernel()

    if args.default_symbols:
        try:
            prog.load_default_debug_info()
        except drgn.MissingDebugInfoError as debug_info_err:
            #
            # If we encounter such an error it means that we can't
            # find the debug info for one or more kernel modules.
            # That's fine because the user may not need those, so
            # print a warning and proceed.
            #
            if not args.quiet:
                print("sdb: " + str(debug_info_err), file=sys.stderr)

    if args.symbol_search:
        try:
            prog.load_debug_info(args.symbol_search)
        except (
            drgn.FileFormatError,
            drgn.MissingDebugInfoError,
            OSError,
        ) as debug_info_err:
            #
            # See similar comment above
            #
            if not args.quiet:
                print("sdb: " + str(debug_info_err), file=sys.stderr)

    return prog


def main() -> None:
    """ The entry point of the sdb "executable" """
    args = parse_arguments()
    prog = setup_target(args)
    repl = REPL(prog, allSDBCommands)
    repl.run()


if __name__ == "__main__":
    main()
