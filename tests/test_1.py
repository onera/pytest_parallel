import pytest_parallel

# TODO run both with 1 and 2 procs and check messages
#@pytest_parallel.mark.parallel(1)
#def test_toto_success(comm):
#  print(f'toto {comm.Get_rank()}')

#@pytest_parallel.mark.parallel(2)
#def test_toto_success(comm):
#  print(f'toto {comm.Get_rank()}')

#@pytest_parallel.mark.parallel(1)
#def test_toto_fail_1(comm):
#  assert 0
#  print(f'toto {comm.Get_rank()}')

#@pytest_parallel.mark.parallel(2)
#def test_toto_2_procs_2_fails(comm):
#  assert 0
#  print(f'toto {comm.Get_rank()}')

@pytest_parallel.mark.parallel(2)
def test_toto_2_procs_1_fail(comm):
  if comm.Get_rank()==0: assert 0
  print(f'toto {comm.Get_rank()}')
