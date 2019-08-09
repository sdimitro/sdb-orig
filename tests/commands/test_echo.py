import drgn
import pytest
import sdb

from typing import Iterable

tplatform = drgn.Platform(drgn.Architecture.UNKNOWN,
                          drgn.PlatformFlags.IS_LITTLE_ENDIAN)
tprog = drgn.Program(tplatform)


def invoke(prog: drgn.Program, objs: Iterable[drgn.Object], line: str) -> Iterable[drgn.Object]:
    """
    Dispatch to sdb.invoke, but also drain the generator it returns, so
    the tests can more easily access the returned objects.
    """
    return [i for i in sdb.invoke(prog, objs, line)]

def test1():
    line = 'echo'
    objs = []

    ret = invoke(tprog, objs, line)

    assert len(ret) == 0

def test2():
    line = 'echo'
    objs = [drgn.Object(tprog, 'void *', value=0)]

    ret = invoke(tprog, objs, line)

    assert len(ret) == 1
    assert ret[0].value_() == 0
    assert ret[0].type_ == tprog.type('void *')

def test3():
    line = 'echo 0x0'
    objs = []

    ret = invoke(tprog, objs, line)

    assert len(ret) == 1
    assert ret[0].value_() == 0
    assert ret[0].type_ == tprog.type('void *')

def test4():
    line = 'echo 0'
    objs = []

    ret = invoke(tprog, objs, line)

    assert len(ret) == 1
    assert ret[0].value_() == 0
    assert ret[0].type_ == tprog.type('void *')

def test5():
    line = 'echo'
    objs = [drgn.Object(tprog, 'int', value=1)]

    ret = invoke(tprog, objs, line)

    assert len(ret) == 1
    assert ret[0].value_() == 1
    assert ret[0].type_ == tprog.type('int')

def test6():
    line = 'echo 1'
    objs = []

    ret = invoke(tprog, objs, line)

    assert len(ret) == 1
    assert ret[0].value_() == 1
    assert ret[0].type_ == tprog.type('void *')

def test7():
    line = 'echo'
    objs = [
        drgn.Object(tprog, 'void *', value=0),
        drgn.Object(tprog, 'int', value=1),
    ]

    ret = invoke(tprog, objs, line)

    assert len(ret) == 2
    assert ret[0].value_() == 0
    assert ret[0].type_ == tprog.type('void *')
    assert ret[1].value_() == 1
    assert ret[1].type_ == tprog.type('int')

def test8():
    line = 'echo 0 1'
    objs = []

    ret = invoke(tprog, objs, line)

    assert len(ret) == 2
    assert ret[0].value_() == 0
    assert ret[0].type_ == tprog.type('void *')
    assert ret[1].value_() == 1
    assert ret[1].type_ == tprog.type('void *')

def test9():
    line = 'echo 0 1'
    objs = [
        drgn.Object(tprog, 'void *', value=0),
        drgn.Object(tprog, 'int', value=1),
    ]

    ret = invoke(tprog, objs, line)

    assert len(ret) == 4
    assert ret[0].value_() == 0
    assert ret[0].type_ == tprog.type('void *')
    assert ret[1].value_() == 1
    assert ret[1].type_ == tprog.type('void *')
    assert ret[2].value_() == 0
    assert ret[2].type_ == tprog.type('void *')
    assert ret[3].value_() == 1
    assert ret[3].type_ == tprog.type('int')
