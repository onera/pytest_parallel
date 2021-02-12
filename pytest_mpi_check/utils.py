
import pytest
from _pytest.nodes import Item

from mpi4py import MPI

# --------------------------------------------------------------------------
def get_n_proc_for_test(item: Item) -> int :
  """
  """
  n_proc_test = 1

  # print("dir(item)::", dir(item))
  try:
    # print("dir(item.callspec)::", dir(item.callspec))
    # print("dir(item)::", dir(item))
    # The way to hooks parametrize : TOKEEP
    # print("parametrize value to use ::", item.callspec.getparam('make_sub_comm'))
    # print("parametrize value to use ::", item.callspec.getparam('sub_comm'))
    # > On pourrai egalement essayer de hooks le vrai communicateur : ici sub_comm == Nombre de rang pour faire le test
    n_proc_test = item.callspec.getparam('sub_comm')
    # print(" ooooo ", item.nodeid, " ---> ", n_proc_test)
  except AttributeError: # No decorator = sequentiel
    pass
  except ValueError:     # No decorator = sequentiel
    pass

  return n_proc_test


# --------------------------------------------------------------------------
def prepare_subcomm_for_tests(items):
  """
  """
  comm   = MPI.COMM_WORLD
  n_rank = comm.size
  i_rank = comm.rank

  beg_next_rank = 0
  for i, item in enumerate(items):
    n_proc_test = get_n_proc_for_test(item)

    # print(item.nodeid, "n_proc_test ::", n_proc_test)
    if(beg_next_rank + n_proc_test > n_rank):
      beg_next_rank = 0

    if(n_proc_test > n_rank):
      item._sub_comm = MPI.COMM_NULL
      continue

    color = MPI.UNDEFINED
    if(i_rank < beg_next_rank+n_proc_test and i_rank >= beg_next_rank):
      color = 1
    comm_split = comm.Split(color)

    if(comm_split != MPI.COMM_NULL):
      assert comm_split.size == n_proc_test
      # print(f"[{i_rank}] Create group with size : {comm_split.size} for test : {item.nodeid}" )

    item._sub_comm = comm_split
    beg_next_rank += n_proc_test
