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


def get_n_proc_for_test(item: Item) -> int :
  try:
    return item.callspec.getparam('comm')
  except AttributeError: # no `comm` fixture => sequential test case
    return 1


def mark_skip(item):
  comm   = MPI.COMM_WORLD
  n_rank = comm.Get_size()

  n_proc_test = get_n_proc_for_test(item)

  skip_msg = f'Not enough procs to execute: {n_proc_test} required but only {n_rank} available'
  item.add_marker(pytest.mark.skip(reason=skip_msg, append=False))


def prepare_subcomm_for_tests(items):
  comm   = MPI.COMM_WORLD
  n_rank = comm.Get_size()
  i_rank = comm.Get_rank()

  beg_next_rank = 0
  for item in items:
    n_proc_test = get_n_proc_for_test(item)

    if n_proc_test > n_rank:
      item._sub_comm = MPI.COMM_NULL
    else:
      if beg_next_rank + n_proc_test > n_rank:
        beg_next_rank = 0

      if beg_next_rank <= i_rank and i_rank < beg_next_rank+n_proc_test :
        color = 1
      else:
        color = MPI.UNDEFINED

      comm_split = comm.Split(color)

      if comm_split != MPI.COMM_NULL:
        assert comm_split.Get_size() == n_proc_test

      item._sub_comm = comm_split
      beg_next_rank += n_proc_test


def filter_items(items):
  comm   = MPI.COMM_WORLD
  n_rank = comm.Get_size()

  filtered_list = []
  for item in items:
    # keep the test on the current proc if the proc belongs to the test sub-comm
    if item._sub_comm != MPI.COMM_NULL:
      filtered_list.append(item)

    # mark the test as `skip` if its required number of procs is too big 
    # but keep the test on proc 0 so it is still reported as skip
    n_proc_test = get_n_proc_for_test(item)
    if n_proc_test > n_rank:
      mark_skip(item)
      if comm.Get_rank() == 0:
        filtered_list.append(item)

  return filtered_list
