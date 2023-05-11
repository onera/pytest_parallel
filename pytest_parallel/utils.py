import sys
import pytest
from _pytest.nodes import Item

from mpi4py import MPI


# TODO backward compatibility begin
def get_callspec_param(callspec, param):
    try:
        return callspec.getparam(param)
    except ValueError:
        return None


def get_n_proc_for_test(item: Item) -> int:
    if hasattr(item, "callspec"):
        comm_size = get_callspec_param(item.callspec, "comm")
        if comm_size is not None:
            return comm_size
        comm_size = get_callspec_param(item.callspec, "sub_comm")
        if comm_size is not None:
            return comm_size
    return 1


# TODO backward compatibility end

# def get_n_proc_for_test(item: Item) -> int :
#  if not hasattr(item, 'callspec'): return 1 # no callspec, so no `comm` => sequential test case
#  try:
#    return item.callspec.getparam('comm')
#  except ValueError: # no `comm` => sequential test case
#    return 1


def add_n_procs(items):
    for item in items:
        item.n_proc = get_n_proc_for_test(item)


def mark_skip(item):
    comm = MPI.COMM_WORLD
    n_rank = comm.Get_size()
    n_proc_test = get_n_proc_for_test(item)
    skip_msg = f"Not enough procs to execute: {n_proc_test} required but only {n_rank} available"
    item.add_marker(pytest.mark.skip(reason=skip_msg), append=False)
    item.marker_mpi_skip = True


def is_dyn_master_process(comm):
    parent_comm = comm.Get_parent()
    if parent_comm == MPI.COMM_NULL:
        return False
    return True


def is_master_process(comm, scheduler):
    if scheduler == "dynamic":
        return is_dyn_master_process(comm)
    return comm.Get_rank() == 0


def spawn_master_process(global_comm):
    if not is_dyn_master_process(global_comm):
        error_codes = []
        if sys.argv[0].endswith(".py"):
            inter_comm = global_comm.Spawn(
                sys.executable, args=sys.argv, maxprocs=1, errcodes=error_codes
            )
        else:
            inter_comm = global_comm.Spawn(
                sys.argv[0], args=sys.argv[1:], maxprocs=1, errcodes=error_codes
            )
        for error_code in error_codes:
            if error_code != 0:
                assert 0
        return inter_comm
    return global_comm.Get_parent()


def number_of_working_processes(comm):
    if is_dyn_master_process(comm):
        return comm.Get_remote_size()
    return comm.Get_size()
