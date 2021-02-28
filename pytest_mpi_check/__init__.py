
__version__ = "0.1"

# export PYTHONUNBUFFERED=true

def assert_mpi(comm, rank, cond, *args ):
  if(comm.rank == rank):
    if(isinstance(cond, bool)):
      assert(cond == True)
    else:
      assert(cond(*args) == True)
  else:
    pass
