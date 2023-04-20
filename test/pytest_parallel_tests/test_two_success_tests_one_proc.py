import pytest_parallel

@pytest_parallel.mark.parallel(1)
def test_success_1(comm):
  assert 1

@pytest_parallel.mark.parallel(1)
def test_success_2(comm):
  assert 1
