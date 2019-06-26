# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb
import argparse
from crash.commands.zfs.zfs_init import *
from crash.commands.locator import Locator
from crash.commands.locator import InputHandler
from crash.commands.pretty_printer import PrettyPrinter
from crash.commands.zfs.zfs_util import print_histogram, nicenum, sizeof
from typing import Iterable

class Metaslab(Locator, PrettyPrinter):
    cmdName = 'metaslab'
    inputType = 'metaslab_t *'
    outputType = 'metaslab_t *'

    def __init__(self, args = ""):
        super().__init__()

        try:
            parser = argparse.ArgumentParser(prog='metaslab')
            parser.add_argument('-H', '--histogram',action='store_true',
                    default=False, help='histogram flag' )
            parser.add_argument('-w', '--weight',action='store_true',
                    default=False, help='weight flag' )
            parser.add_argument('metaslab_ids', nargs='*', type=int)
            self.args = parser.parse_args(gdb.string_to_argv(args))
        except:
            pass

    def metaslab_weight_print(msp, print_header, indent):
        if print_header:
            print("".ljust(indent), "ID".rjust(3), "ACTIVE".ljust(6),
                    "ALGORITHM".rjust(9), "FRAG".rjust(4),
                    "ALLOC".rjust(10), "MAXSZ".rjust(10),
                    "WEIGHT".rjust(12))
            print("".ljust(indent), "-" * 65)
        weight = int(msp['ms_weight'])
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

        print("".ljust(indent), str(msp['ms_id']).rjust(3), w.rjust(4),
                "L" if msp['ms_loaded'] else " ", algorithm.rjust(8), end='')
        if msp['ms_fragmentation'] == -1:
            print('-'.rjust(6), end='')
        else:
            print((str(msp['ms_fragmentation']) + "%").rjust(5), end='')
        print(str(str(int(msp['ms_allocated_space']) >> 20) + "M").rjust(7),
            ("(" + str(int(msp['ms_allocated_space']) * 100 / msp['ms_size']) +
            "%)").rjust(5), nicenum(msp['ms_max_size']).rjust(10), end="")

        if (WEIGHT_IS_SPACEBASED(weight)):
            print("", nicenum(weight & ~(METASLAB_ACTIVE_MASK |
                METASLAB_WEIGHT_TYPE)).rjust(12))
        else:
            count = str(WEIGHT_GET_COUNT(weight))
            size = nicenum(1 << WEIGHT_GET_INDEX(weight))
            print("", (count + ' x ' + size).rjust(12))


    def print_metaslab(msp, print_header, indent):
        sm = msp['ms_sm']

        if print_header:
            print("".ljust(indent), "ADDR".ljust(18), "ID".rjust(4),
                    "OFFSET".rjust(16), "FREE".rjust(8), "FRAG".rjust(5),
                    "UCMU".rjust(8))
            print("".ljust(indent), '-' * 65)

        free = msp['ms_size']
        if sm != 0:
            free -= sm['sm_phys']['smp_alloc']

        ufrees = msp['ms_unflushed_frees']['rt_space']
        uallocs = msp['ms_unflushed_allocs']['rt_space']
        free = free + ufrees - uallocs

        uchanges_free_mem = msp['ms_unflushed_frees']['rt_root']['avl_numnodes']
        uchanges_free_mem *= sizeof('range_seg_t')
        uchanges_alloc_mem = msp['ms_unflushed_allocs']['rt_root']['avl_numnodes']
        uchanges_alloc_mem *= sizeof('range_seg_t')
        uchanges_mem = uchanges_free_mem + uchanges_alloc_mem

        print("".ljust(indent), hex(msp).ljust(16),
                str(msp['ms_id']).rjust(4),
                hex(msp['ms_start']).rjust(16),
                nicenum(free).rjust(8), end='')
        if msp['ms_fragmentation'] == -1:
            print('-'.rjust(6), end='')
        else:
            print((str(msp['ms_fragmentation']) + "%").rjust(6), end='')
        print(nicenum(uchanges_mem).rjust(9))


    def pretty_print(self, metaslabs, indent=0):
        first_time = True
        for msp in metaslabs:
            if not self.args.histogram and not self.args.weight:
                Metaslab.print_metaslab(msp, first_time, indent)
            if self.args.histogram:
                sm = msp['ms_sm']
                if sm != 0:
                    histogram = sm['sm_phys']['smp_histogram']
                    print_histogram(histogram, 32, sm['sm_shift'])
            if self.args.weight:
                Metaslab.metaslab_weight_print(msp, first_time, indent)
            first_time = False


# XXX - removed because of circular dependencies when importing Vdev class
#
#    def metaslab_from_spa(self, spa):
#        vdevs = SDBCommand.executePipeline([spa], [Vdev()])
#        for vd in vdevs:
#            yield from self.metaslab_from_vdev(vd)

    @InputHandler('vdev_t*')
    def from_vdev(self, vdev : gdb.Value) -> Iterable[gdb.Value]:
        if self.args.metaslab_ids:
            # yield the requested metaslabs
            for id in self.args.metaslab_ids:
                if id >= vdev['vdev_ms_count']:
                    raise TypeError('metaslab id {} not valid; there are only {} metaslabs in vdev id {}'.format(
                        id,
                        vdev['vdev_ms_count'],
                        vdev['vdev_id']))
                yield vdev['vdev_ms'][id]
        else:
            for m in range(0, int(vdev['vdev_ms_count'])):
                msp = vdev['vdev_ms'][m]
                yield msp
