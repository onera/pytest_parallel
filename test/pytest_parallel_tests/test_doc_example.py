import time
import pytest_parallel


@pytest_parallel.mark.parallel(2)
def test_A(comm):
    time.sleep(0.1)
    if comm.rank == 1:
        assert False


def test_B():
    time.sleep(1)
    assert True


@pytest_parallel.mark.parallel(3)
def test_C(comm):
    time.sleep(0.2)
    assert comm.size == 3


def test_D():
    time.sleep(0.5)
    assert False
