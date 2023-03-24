import pytest
from _pytest.nodes import Item

from mpi4py import MPI

def terminate_with_no_exception(error_msg):
  """
  Print an error message and terminates the program without launching an exception
  PyTest does not support exceptions being thrown from virtually all `pytest_` hooks
  """
  import os
  import sys

  print(error_msg, file=sys.stderr)
  os._exit(1)

# --------------------------------------------------------------------------

def get_n_proc_for_test(item: Item) -> int :
  try:
    return item.callspec.getparam('comm')
  except AttributeError: # no `comm` fixture => sequential test case
    return 1

# --------------------------------------------------------------------------
def prepare_subcomm_for_tests(items):
  """
  """
  comm   = MPI.COMM_WORLD
  n_rank = comm.Get_size()
  i_rank = comm.Get_rank()

  beg_next_rank = 0
  for item in items:
    n_proc_test = get_n_proc_for_test(item)

    # print(item.nodeid, "n_proc_test ::", n_proc_test)
    if beg_next_rank + n_proc_test > n_rank:
      beg_next_rank = 0

    if n_proc_test > n_rank:
      item._sub_comm = MPI.COMM_NULL
      # item._sub_comm = -1 # None
      continue

    color = MPI.UNDEFINED
    if(i_rank < beg_next_rank+n_proc_test and i_rank >= beg_next_rank):
      color = 1
    comm_split = comm.Split(color)

    if(comm_split != MPI.COMM_NULL):
      assert comm_split.size == n_proc_test
      # print(f"[{i_rank}] Create group with size : {comm_split.size} for test : {item.nodeid}" )
    else:
      assert(comm_split == MPI.COMM_NULL)

    item._sub_comm = comm_split
    beg_next_rank += n_proc_test
