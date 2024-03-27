import sys
from mpi4py import MPI


def is_dyn_master_process(comm):
    parent_comm = comm.Get_parent()
    if parent_comm == MPI.COMM_NULL:
        return False
    return True


def should_enable_terminal_reporter(comm, scheduler):
    if scheduler == "dynamic":
        return is_dyn_master_process(comm)
    else:
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
