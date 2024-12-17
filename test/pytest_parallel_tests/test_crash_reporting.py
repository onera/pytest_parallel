# TODO These test file was used to develop crash reporting when scheduler=shell or scheduler=slurm,
# but it is not currently integrated to the pytest_parallel test suite
import pytest_parallel
import signal

def test_seq_pass():
  assert 1

def test_seq_fail():
  assert 0

def test_seq_crash():
  signal.raise_signal(11) # SIGSEGV


@pytest_parallel.mark.parallel(2)
def test_par_pass(comm):
  assert 1

@pytest_parallel.mark.parallel(2)
def test_par_fail(comm):
  assert 0

@pytest_parallel.mark.parallel(2)
def test_par_pass_fail(comm):
  if comm.rank==0:
    assert 1
  if comm.rank==1:
    assert 0



@pytest_parallel.mark.parallel(2)
def test_par_crash(comm):
  signal.raise_signal(11) # SIGSEGV

@pytest_parallel.mark.parallel(2)
def test_par_pass_crash(comm):
  if comm.rank==1:
    assert 1
  if comm.rank==1:
    signal.raise_signal(11) # SIGSEGV

@pytest_parallel.mark.parallel(2)
def test_par_crash_fail(comm):
  if comm.rank==1:
    signal.raise_signal(11) # SIGSEGV
  if comm.rank==1:
    assert 0
