import pytest

@pytest.fixture
def comm(request):
  """
  Only return a previous MPI Communicator (build at prepare step )
  """
  return request._pyfuncitem._sub_comm

def parallel(n_proc_list):
  if isinstance(n_proc_list,int):
    n_proc_list = [n_proc_list]
  def mark_mpi_test_impl(tested_fun):
    return pytest.mark.parametrize("comm", n_proc_list, indirect=['comm']) (
          (tested_fun)
        )
  return mark_mpi_test_impl
