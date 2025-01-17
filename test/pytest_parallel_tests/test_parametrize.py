import pytest
import pytest_parallel


@pytest_parallel.mark.parallel([1, 2])
def test_mark_mpi_decorator_with_list(comm):
    assert comm.Get_size() == 1 or comm.Get_size() == 2


@pytest.mark.parametrize("val", [3, 4])
@pytest_parallel.mark.parallel(2)
def test_mark_mpi_decorator_with_other_pytest_deco(comm, val):
    assert comm.Get_size() == 2
    assert val == 3 or val == 4


@pytest.mark.parametrize("val", [3, 4])
@pytest_parallel.mark.parallel([1, 2])
def test_mark_mpi_decorator_with_list_and_other_pytest_deco(comm, val):
    assert comm.Get_size() == 1 or comm.Get_size() == 2
    assert val == 3 or val == 4
