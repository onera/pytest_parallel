import pytest_parallel

# TODO run both with 1 and 2 procs and check messages
@pytest_parallel.mark.parallel(2)
def test_toto(comm):
  print(f'toto {comm.Get_rank()}')
