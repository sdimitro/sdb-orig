import drgn
import pytest
import sdb.command as sdbc

from typing import Iterable

tplatform = drgn.Platform(drgn.Architecture.UNKNOWN,
                          drgn.PlatformFlags.IS_LITTLE_ENDIAN)
tprog = drgn.Program(tplatform)


def get_cmd(cmd: str, args: str = '') -> sdbc.SDBCommand:
    if args == '':
        return sdbc.allSDBCommands[cmd](tprog)
    else:
        return sdbc.allSDBCommands[cmd](tprog, args)


def drain_generator(generator):
    return [x for x in generator]


def call_cmd(cmd: str, istream: Iterable[drgn.Object], args: str):
    return drain_generator(get_cmd(cmd, args).call(istream))


def test_echo():
    val = call_cmd('echo', [], '')
    assert len(val) == 0

    obj = drgn.Object(tprog, 'void *', value=0)
    val = call_cmd('echo', [obj], '')
    assert len(val) == 1
    assert val[0].value_() == 0
    assert str(val[0].type_) == 'void *'

    val = call_cmd('echo', [], '0x0')
    assert len(val) == 1
    assert val[0].value_() == 0
    assert str(val[0].type_) == 'void *'

    val = call_cmd('echo', [], '0')
    assert len(val) == 1
    assert val[0].value_() == 0
    assert str(val[0].type_) == 'void *'

    obj2 = drgn.Object(tprog, 'int', value=1)
    val = call_cmd('echo', [obj2], '')
    assert len(val) == 1
    assert val[0].value_() == 1
    assert str(val[0].type_) == 'int'

    val = call_cmd('echo', [], '1')
    assert len(val) == 1
    assert val[0].value_() == 1
    assert str(val[0].type_) == 'void *'

    val = call_cmd('echo', [obj, obj2], '')
    assert len(val) == 2
    assert val[0].value_() == 0
    assert str(val[0].type_) == 'void *'
    assert val[1].value_() == 1
    assert str(val[1].type_) == 'int'

    val = call_cmd('echo', [], '0 1')
    assert len(val) == 2
    assert val[0].value_() == 0
    assert str(val[0].type_) == 'void *'
    assert val[1].value_() == 1
    assert str(val[1].type_) == 'void *'

    val = call_cmd('echo', [obj, obj2], '0 1')
    assert len(val) == 4
    assert val[0].value_() == 0
    assert str(val[0].type_) == 'void *'
    assert val[1].value_() == 1
    assert str(val[1].type_) == 'void *'
    assert val[2].value_() == 0
    assert str(val[2].type_) == 'void *'
    assert val[3].value_() == 1
    assert str(val[3].type_) == 'int'
