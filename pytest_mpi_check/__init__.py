
__version__ = "0.1"


def assert_mpi(comm, rank, cond ):
  if(comm.rank == rank):
    assert(cond == True)
  else:
    pass
