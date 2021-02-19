import pytest
from decorator import decorate
from mpi4py import MPI

@pytest.fixture
def sub_comm(request):
  """
  Only return a previous MPI Communicator (build at prepare step )
  """
  return request._pyfuncitem._sub_comm

# def exit_if_null_comm(tested_fun):
#   def exit_if_null_comm_impl(_,sub_comm,*args,**kwargs):
#     if sub_comm == MPI.COMM_NULL :
#       return
#     print(tested_fun)
#     tested_fun(sub_comm,*args,**kwargs)
#   # preserve the tested_fun named arguments signature for use by other pytest decorator
#   tested_fun_replica = decorate(tested_fun,exit_if_null_comm_impl)
#   return tested_fun_replica

def mark_mpi_test(n_proc_list):
  if type(n_proc_list)==int: # Replace by isinstance
    n_proc_list = [n_proc_list]
  max_n_proc = max(n_proc_list)
  def mark_mpi_test_impl(tested_fun):
    return pytest.mark.parametrize("sub_comm", n_proc_list, indirect=['sub_comm']) (
          (tested_fun)
        )
  return mark_mpi_test_impl
