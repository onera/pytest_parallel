from mpi4py import MPI

# Supposed to be launched with n_procs == 2
# This is a sanity test: not the usual way to run pytest_parallel,
# but to see if it is ok to run in parallel without using the plugin's logic
def test_success_fail():
  comm = MPI.COMM_WORLD
  if comm.Get_rank()==0: assert True
  if comm.Get_rank()==1: assert True









