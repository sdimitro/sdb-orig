# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
#
# TODO - add dva command
#

import gdb
from crash.commands.zfs.zfs_init import *
from crash.commands.pretty_printer import PrettyPrinter
from crash.commands.zfs.zfs_util import enum_lookup
from typing import Callable

class Blkptr(PrettyPrinter):
    """pretty print a zfs blkptr_t

NAME
  blkptr - display a zfs block pointer

SYNOPSIS
  cast blkptr_t* <address> | blkptr
  """

    cmdName = 'blkptr'
    inputType = 'blkptr_t *'
    def __init__(self, arg=""):
        super().__init__()

    def print_blkptr_hole(bp, type):
        print("HOLE [L{:d} {}] size={:x}L birth={}L".format(
            int(BP_GET_LEVEL(bp)),
            type,
            int(BP_GET_LSIZE(bp)),
            bp['blk_birth']))

    def print_blkptr_redacted(bp, type):
        print("REDACTED [L{:d} {}] size={:x}L birth={}L".format(
            int(BP_GET_LEVEL(bp)),
            type,
            int(BP_GET_LSIZE(bp)),
            bp['blk_birth']))

    def print_blkptr_embedded(bp, type):
        print("EMBEDDED [L{:d} {}] et={} {} size={:x}L/{:x}P birth={}L".format(
            int(BP_GET_LEVEL(bp)),
            type,
            BPE_GET_ETYPE(bp),
            enum_lookup("enum zio_compress", BP_GET_COMPRESS(bp)),
            int(BPE_GET_LSIZE(bp)),
            int(BPE_GET_PSIZE(bp)),
            bp['blk_birth']))

    def print_blkptr_normal(bp, type):
        copyname = ["zero", "single", "double", "triple"]
        copies = 0

        for d in range(SPA_DVAS_PER_BP):
            dva = bp['blk_dva'][d]
            if DVA_GET_ASIZE(dva) == 0:
                break
            copies += 1
            print("DVA[{:d}]=<{:d}:{:x}:{:x}>".format(d,
                int(DVA_GET_VDEV(dva)),
                int(DVA_GET_OFFSET(dva)),
                int(DVA_GET_ASIZE(dva))))

        print("[L{} {}] {} {} {} {} {} {}".format(
            BP_GET_LEVEL(bp),
            type,
            enum_lookup("enum zio_checksum", BP_GET_CHECKSUM(bp)),
            enum_lookup("enum zio_compress", BP_GET_COMPRESS(bp)),
            'BE' if BP_GET_BYTEORDER(bp) == 0 else 'LE',
            'gang' if BP_IS_GANG(bp) else 'contiguous',
            'dedup' if BP_GET_DEDUP(bp) else 'unique',
            copyname[copies]))

        print("size={:x}L/{:x}P birth={}L/{}P fill={}".format(
            int(BP_GET_LSIZE(bp)),
            int(BP_GET_PSIZE(bp)),
            bp['blk_birth'],
            BP_PHYSICAL_BIRTH(bp),
            BP_GET_FILL(bp)))
        print("cksum={:x}:{:x}:{:x}:{:x}".format(
            int(bp['blk_cksum']['zc_word'][0]),
            int(bp['blk_cksum']['zc_word'][1]),
            int(bp['blk_cksum']['zc_word'][2]),
            int(bp['blk_cksum']['zc_word'][3])))

    def pretty_print(self, bps):
        for bp in bps:
            if bp == 0:
                print("<NULL>")
                return

            type = enum_lookup("enum dmu_object_type", BP_GET_TYPE(bp))

            if BP_IS_HOLE(bp):
                Blkptr.print_blkptr_hole(bp, type)
            elif BP_IS_REDACTED(bp):
                Blkptr.print_blkptr_redacted(bp, type)
            elif BP_IS_EMBEDDED(bp):
                Blkptr.print_blkptr_embedded(bp, type)
            else:
                Blkptr.print_blkptr_normal(bp, type)
