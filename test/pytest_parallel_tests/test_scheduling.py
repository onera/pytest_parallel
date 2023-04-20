import pytest_parallel
import time

#time_base = 1.0
time_base = 0.01

@pytest_parallel.mark.parallel(2)
def test_0(comm):
  time.sleep(time_base)

@pytest_parallel.mark.parallel(2)
def test_1(comm):
  time.sleep(10*time_base)

@pytest_parallel.mark.parallel(3)
def test_2(comm):
  time.sleep(time_base)

@pytest_parallel.mark.parallel(1)
def test_3(comm):
  time.sleep(10*time_base)

@pytest_parallel.mark.parallel(1)
def test_4(comm):
  time.sleep(time_base)

@pytest_parallel.mark.parallel(1)
def test_5(comm):
  time.sleep(time_base)

@pytest_parallel.mark.parallel(2)
def test_6(comm):
  time.sleep(time_base)

@pytest_parallel.mark.parallel(2)
def test_7(comm):
  time.sleep(time_base)
