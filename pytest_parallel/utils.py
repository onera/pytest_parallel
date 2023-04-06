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


def add_n_procs(items):
  for item in items:
    item._n_mpi_proc = get_n_proc_for_test(item)

def group_items_by_parallel_steps(items, n_workers):
  add_n_procs(items)
  items.sort(key=lambda item: item._n_mpi_proc, reverse=True)

  remaining_n_procs_by_step = []
  items_by_step = []
  items_to_skip = []
  for item in items:
    if item._n_mpi_proc > n_workers[i]:
      items_to_skip += [item]
    else:
      found_step = False
      for i in range(len(remaining_n_procs_by_step)):
        if item._n_mpi_proc <= remaining_n_procs_by_step[i]:
          items_by_step[i] += [item]
          remaining_n_procs_by_step[i] -= item._n_mpi_proc
          found_step = True
          break
      if not found_step:
        items_by_step += [[item]]
        remaining_n_procs_by_step += [n_worker - item._n_mpi_proc]

  return items_by_step, items_to_skip



def mark_skip(item):
  comm   = MPI.COMM_WORLD
  n_rank = comm.Get_size()

  n_proc_test = get_n_proc_for_test(item)

  skip_msg = f'Not enough procs to execute: {n_proc_test} required but only {n_rank} available'
  item.add_marker(pytest.mark.skip(reason=skip_msg, append=False))


#def prepare_subcomm_for_tests(items):
#  comm   = MPI.COMM_WORLD
#  n_rank = comm.Get_size()
#  i_rank = comm.Get_rank()
#
#  beg_next_rank = 0
#  for item in items:
#    n_proc_test = get_n_proc_for_test(item)
#
#    if n_proc_test > n_rank: # not enough procs: will be skipped
#      if comm.Get_rank() == 0:
#        item._sub_comm = MPI.COMM_SELF
#      else:
#        item._sub_comm = MPI.COMM_NULL
#    else:
#      if beg_next_rank + n_proc_test > n_rank:
#        beg_next_rank = 0
#
#      if beg_next_rank <= i_rank and i_rank < beg_next_rank+n_proc_test :
#        color = 1
#      else:
#        color = MPI.UNDEFINED
#
#      comm_split = comm.Split(color)
#
#      if comm_split != MPI.COMM_NULL:
#        assert comm_split.Get_size() == n_proc_test
#
#      item._sub_comm = comm_split
#      beg_next_rank += n_proc_test


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
      if item._sub_comm == MPI.COMM_SELF:
        mark_skip(item)

  return filtered_list









def is_master_process(comm):
  parent_comm = comm.Get_parent();
  if parent_comm == MPI.COMM_NULL:
    return False
  else:
    return True


def spawn_master_process(global_comm):
    if is_master_process(global_comm):
      error_codes = []
      inter_comm = global_comm.Spawn(sys.argv[0], args=sys.argv[1:], maxprocs=1, errcodes=error_codes)
      for error_code in error_codes:
        if error_code != 0:
          assert 0, 'spawn_master_process error' # TODO pytest error reporting
      return inter_comm
    else:
      return global_comm.Get_parent()

def number_of_working_processes(comm):
  if is_master_process(comm):
    return comm.Get_remote_size(comm);
  else:
    return comm.Get_size()
