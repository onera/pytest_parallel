import pytest
import pytest_parallel
from mpi4py import MPI

@pytest_parallel.mark.parallel(1)
def test_mark_mpi_decorator(comm):
  assert comm != MPI.COMM_NULL
  assert comm.Get_rank() == 0
  assert comm.Get_size() == 1

@pytest_parallel.mark.parallel([1,2])
def test_mark_mpi_decorator_with_list(comm):
  assert comm.Get_size() == 1 || comm.Get_size() == 2


@pytest.mark.parametrize("val",[3,4])
@pytest_parallel.mark.parallel(2)
def test_mark_mpi_decorator_with_other_pytest_deco(comm,val):
  assert comm.Get_size() == 2
  assert val == 3 || val == 4

@pytest.mark.parametrize("val",[3,4])
@pytest_parallel.mark.parallel([1,2])
def test_mark_mpi_decorator_with_list_and_other_pytest_deco(comm,val):
  assert comm.Get_size() == 1 || comm.Get_size() == 2
  assert val == 3 || val == 4
