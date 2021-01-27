# -*- coding: utf-8 -*-

import pytest
from mpi4py import MPI
from _pytest.nodes import Item
import sys


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
  # print("dir(item)::", dir(item))
  # print("dir(item)::", dir(item.callspec))
  try:
    # The way to hooks parametrize : TOKEEP
    # print("parametrize value to use ::", item.callspec.getparam('make_sub_comm'))
    pass
  except AttributeError:
    pass
  except ValueError:
    pass
  # exit(2)
  # print("dir(item)::", dir(item.keywords))
  for mark in item.iter_markers(name="mpi_test"):
    if mark.args:
      raise ValueError("mpi mark does not take positional args")
    n_proc_test = mark.kwargs.get('comm_size')

    # print("**** item:: ", dir(item))
    # print("**** request:: ", dir(item._pyfuncitem))
    # print("**** request:: ", dir(item._pyfuncitem.funcargnames))
    # print("**** request:: ", item._pyfuncitem.funcargnames)
    # print("**** request:: ", item._pyfuncitem.funcargs)
    # print("mark.kwargs::", mark.kwargs)
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

    # print("n_proc_test ::", n_proc_test)
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
      # print(f"[{i_rank}] Create group with size : {comm_split.size} for test : {item.nodeid}" )

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
  # print("Mon super sous-modules")
  prepare_subcomm_for_tests(session)

  # for i, item in enumerate(session.items):
  #   print(dir(item))
  #   pytest.pytest_runtest_protocol(item)
  #   print("*"*10)
  #   pass

  comm = MPI.COMM_WORLD
  # print("pytest_runtestloop", comm.rank)
  # print(dir(session.session))
  for i, item in enumerate(session.items):
    # if(comm.rank == i):
      # print("***************************", item.nodeid)
      # print("***************************", item._sub_comm)
      # print(i, item, dir(item), item.name, item.originalname)
      # print("launch on {0} item : {1}".format(comm.rank, item))
      # print(i, item)

      # temp_ouput_file = 'maia_'
      # sys.stdout = open(f"{temp_ouput_file(item.name)}_{MPI.COMM_WORLD.Get_rank()}", "w")
      # sys.stdout = open(f"maia_{item.name}_{MPI.COMM_WORLD.Get_rank()}", "w")
      # item.toto = i
      # Create sub_comm !
      item.config.hook.pytest_runtest_protocol(item=item, nextitem=None)
      if session.shouldfail:
        raise session.Failed(session.shouldfail)
      if session.shouldstop:
        raise session.Interrupted(session.shouldstop)
  return True

