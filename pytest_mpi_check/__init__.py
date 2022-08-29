__version__ = "0.1"

import pytest_mpi_check.mark

def assert_mpi(comm, rank, cond, *args):
  if comm.rank == rank:
    if isinstance(cond, bool):
      assert cond
    else:
      assert cond(*args)
  else:
    pass
