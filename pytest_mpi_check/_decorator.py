import pytest
from decorator import decorate
from mpi4py import MPI

@pytest.fixture
def sub_comm(request):
  """
  Only return a previous MPI Communicator (build at prepare step )
  """
  return request._pyfuncitem._sub_comm

def mark_mpi_test(n_proc_list):
  if type(n_proc_list)==int: # Replace by isinstance
    n_proc_list = [n_proc_list]
  max_n_proc = max(n_proc_list)
  def mark_mpi_test_impl(tested_fun):
    return pytest.mark.parametrize("sub_comm", n_proc_list, indirect=['sub_comm']) (
          (tested_fun)
        )
  return mark_mpi_test_impl
