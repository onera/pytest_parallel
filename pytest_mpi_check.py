# -*- coding: utf-8 -*-

import pytest
from mpi4py import MPI
from _pytest.nodes import Item


def pytest_addoption(parser):
  group = parser.getgroup('mpi-check')
  group.addoption(
                  '--foo',
                  action='store',
                  dest='dest_foo',
                  default='2020',
                  help='Set the value for the fixture "bar".'
                  )

  parser.addini('HELLO', 'Dummy pytest.ini setting')


# --------------------------------------------------------------------------
def get_n_proc_for_test(item: Item) -> int :
  """
  """
  n_proc_test = 1
  for mark in item.iter_markers(name="mpi_test"):
    if mark.args:
      raise ValueError("mpi mark does not take positional args")
    n_proc_test = mark.kwargs.get('comm_size')
    if(n_proc_test is None):
      raise ValueError("We need to specify a comm_size for the test")
  return n_proc_test

# --------------------------------------------------------------------------
def prepare_subcomm_for_tests(session):
  """
  """
  comm   = MPI.COMM_WORLD
  n_rank = comm.size
  i_rank = comm.rank

  # print(dir(comm))
  # print(dir(MPI))
  # print(help(comm.Dup))
  # print(help(comm.Split))
  # comm_split = comm.Split(comm.rank)
  # print("comm_dub:: ", comm_split.size)

  # > Sort
  # for i, item in enumerate(session.items):

  beg_next_rank = 0
  for i, item in enumerate(session.items):
    n_proc_test = get_n_proc_for_test(item)

    #print("n_proc_test ::", n_proc_test)
    if(beg_next_rank + n_proc_test > n_rank):
      beg_next_rank = 0

    if(n_proc_test > n_rank):
      continue

    # MPI.UNDEFINED
    color = MPI.UNDEFINED
    if(i_rank < beg_next_rank+n_proc_test and i_rank >= beg_next_rank):
      color = 1
    comm_split = comm.Split(color)

    if(comm_split != MPI.COMM_NULL):
      assert comm_split.size == n_proc_test
      #print(f"[{i_rank}] Create group with size : {comm_split.size} for test : {item.nodeid}" )

    item._sub_comm = comm_split
    beg_next_rank += n_proc_test

# --------------------------------------------------------------------------
# 100 Workers
#  1    2    3    4    5   6   7
# 45 | 45 | 10 | 15 | 10 | 5 | 5

# 45 | 45 | 10  --> Phase

# window : 1 1 1 0 0 0 0
# window : 1 1 2 0 0 0 0 --> Communique MPI_Accumulate()


# --------------------------------------------------------------------------
@pytest.mark.tryfirst
def pytest_runtestloop(session):
  """
  """
  #print("Mon super sous-modules")
  prepare_subcomm_for_tests(session)

  for i, item in enumerate(session.items):
    #print(i)
    pass

  return True
