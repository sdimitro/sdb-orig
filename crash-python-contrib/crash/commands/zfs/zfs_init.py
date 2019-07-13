# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

from typing import Callable
import gdb

SPA_MINBLOCKSHIFT = 9

SPA_LSIZEBITS = 16
SPA_PSIZEBITS = 16
SPA_ASIZEBITS = 24

SPA_COMPRESSBITS = 7
SPA_VDEVBITS =     24

SPA_DVAS_PER_BP = 3

BP_EMBEDDED_TYPE_DATA = 0
BP_EMBEDDED_TYPE_MOOCH_BYTESWAP = 1
BP_EMBEDDED_TYPE_REDACTED = 2
ZIO_CHECKSUM_OFF = 2

P2PHASE : Callable[[gdb.Value, int], gdb.Value]			= lambda x, align : ((x) & ((align) - 1))
BF64_DECODE : Callable[[gdb.Value, int, int], int]	= lambda x, low, len : int(P2PHASE(x >> low, 1 << len))
BF64_GET : Callable[[gdb.Value, int, int], int]		= lambda x, low, len : BF64_DECODE(x, low, len)
BF64_GET_SB : Callable[[gdb.Value, int, int, int, int], int]	= lambda x, low, len, shift, bias : (BF64_GET(x, low, len) + bias) << shift

DVA_GET_ASIZE : Callable[[gdb.Value], int]	= lambda dva : BF64_GET_SB(dva['dva_word'][0], 0, SPA_ASIZEBITS, SPA_MINBLOCKSHIFT, 0)
DVA_GET_VDEV : Callable[[gdb.Value], int]		= lambda dva : BF64_GET(dva['dva_word'][0], 32, SPA_VDEVBITS)
DVA_GET_OFFSET : Callable[[gdb.Value], int]	= lambda dva : BF64_GET_SB(dva['dva_word'][1], 0, 63, SPA_MINBLOCKSHIFT, 0)
DVA_IS_EMPTY : Callable[[gdb.Value], bool]		= lambda dva : dva['dva_word'][0] == 0 and dva['dva_word'][1] == 0

BP_IS_GANG : Callable[[gdb.Value], bool]	= lambda bp : False if BP_IS_EMBEDDED(bp) else True
BP_IS_HOLE : Callable[[gdb.Value], bool]	= lambda bp : not BP_IS_EMBEDDED(bp) and DVA_IS_EMPTY(bp['blk_dva'][0])
BP_IS_REDACTED : Callable[[gdb.Value], bool]	= lambda bp : BP_IS_EMBEDDED(bp) and BPE_GET_ETYPE(bp) == BP_EMBEDDED_TYPE_REDACTED

BPE_GET_ETYPE : Callable[[gdb.Value], int]	= lambda bp : BF64_GET(bp['blk_prop'], 40, 8)
BPE_GET_LSIZE : Callable[[gdb.Value], int]	= lambda bp : BF64_GET_SB(bp['blk_prop'], 0, 25, 0, 1)
BPE_GET_PSIZE = lambda bp : BF64_GET_SB(bp['blk_prop'], 25, 7, 0, 1)

BP_GET_LSIZE = lambda bp : BPE_GET_LSIZE(bp) if BP_IS_EMBEDDED(bp) else BF64_GET_SB(bp['blk_prop'], 0, SPA_LSIZEBITS, SPA_MINBLOCKSHIFT, 1)
BP_GET_PSIZE = lambda bp : 0 if BP_IS_EMBEDDED(bp) else BF64_GET_SB(bp['blk_prop'], 16, SPA_PSIZEBITS, SPA_MINBLOCKSHIFT, 1)

BP_GET_COMPRESS =   lambda bp : BF64_GET(bp['blk_prop'], 32, SPA_COMPRESSBITS)
BP_IS_EMBEDDED : Callable[[gdb.Value], bool] =    lambda bp : bool(BF64_GET(bp['blk_prop'], 39, 1))
BP_GET_CHECKSUM =   lambda bp : ZIO_CHECKSUM_OFF if BP_IS_EMBEDDED(bp) else BF64_GET(bp['blk_prop'], 40, 8)
BP_GET_TYPE =       lambda bp : BF64_GET(bp['blk_prop'], 48, 8)
BP_GET_LEVEL =      lambda bp : BF64_GET(bp['blk_prop'], 56, 5)
BP_GET_DEDUP =      lambda bp : BF64_GET(bp['blk_prop'], 62, 1)
BP_GET_BYTEORDER =  lambda bp : BF64_GET(bp['blk_prop'], 63, 1)
BP_PHYSICAL_BIRTH = lambda bp : 0 if BP_IS_EMBEDDED(bp) else bp['blk_phys_birth'] if bp['blk_phys_birth'] else bp['blk_birth']
BP_GET_FILL =       lambda bp : 1 if BP_IS_EMBEDDED(bp) else bp['blk_fill']

WEIGHT_IS_SPACEBASED = lambda weight : weight == 0 or BF64_GET(weight, 60, 1)
WEIGHT_GET_INDEX = lambda weight : BF64_GET((weight), 54, 6)
WEIGHT_GET_COUNT = lambda weight : BF64_GET((weight), 0, 54)

METASLAB_WEIGHT_PRIMARY = int(1 << 63)
METASLAB_WEIGHT_SECONDARY = int(1 << 62)
METASLAB_WEIGHT_CLAIM = int(1 << 61)
METASLAB_WEIGHT_TYPE = int(1 << 60)
METASLAB_ACTIVE_MASK = METASLAB_WEIGHT_PRIMARY | METASLAB_WEIGHT_SECONDARY  | METASLAB_WEIGHT_CLAIM
