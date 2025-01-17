import pytest_parallel


@pytest_parallel.mark.parallel(2)
def test_fail_one_rank(comm):
    if comm.rank == 0:
        assert 0
    if comm.rank == 1:
        assert 1
