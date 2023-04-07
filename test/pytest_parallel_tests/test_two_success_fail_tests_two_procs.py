import pytest_parallel

@pytest_parallel.mark.parallel(2)
def test_success_1(comm):
  assert 1

@pytest_parallel.mark.parallel(2)
def test_fail_2(comm):
  assert 0
