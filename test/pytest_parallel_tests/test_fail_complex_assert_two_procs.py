import pytest_parallel
import numpy as np

@pytest_parallel.mark.parallel(2)
def test_fail_with_complex_assert_reporting(comm):
    if comm.Get_rank() == 0:
        assert 1 == 0
    if comm.Get_rank() == 1:
        assert (np.array([0,1,2]) == np.array([0,1,3])).all()
