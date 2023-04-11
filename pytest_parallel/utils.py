import pytest
from _pytest.nodes import Item

from mpi4py import MPI
import sys


def get_n_proc_for_test(item: Item) -> int :
  try:
    return item.callspec.getparam('comm')
  except AttributeError: # no `comm` fixture => sequential test case
    return 1


def add_n_procs(items):
  for item in items:
    item._n_mpi_proc = get_n_proc_for_test(item)

def mark_skip(item):
  comm   = MPI.COMM_WORLD
  n_rank = comm.Get_size()

  n_proc_test = get_n_proc_for_test(item)

  skip_msg = f'Not enough procs to execute: {n_proc_test} required but only {n_rank} available'
  item.add_marker(pytest.mark.skip(reason=skip_msg, append=False))
  item._mpi_skip = True











def is_dyn_master_process(comm):
  parent_comm = comm.Get_parent();
  if parent_comm == MPI.COMM_NULL:
    return False
  else:
    return True

def is_master_process(comm, scheduler):
  if scheduler == 'dynamic':
    return is_dyn_master_process(comm)
  else:
    return comm.Get_rank() == 0

def spawn_master_process(global_comm):
    if not is_dyn_master_process(global_comm):
      error_codes = []
      inter_comm = global_comm.Spawn(sys.argv[0], args=sys.argv[1:], maxprocs=1, errcodes=error_codes)
      for error_code in error_codes:
        if error_code != 0:
          assert 0
      return inter_comm
    else:
      return global_comm.Get_parent()

def number_of_working_processes(comm):
  if is_dyn_master_process(comm):
    return comm.Get_remote_size();
  else:
    return comm.Get_size()
