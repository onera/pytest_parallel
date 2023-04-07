import pytest

from mpi4py import MPI

from _pytest._code.code import ExceptionChainRepr, ReprTraceback, ReprEntry, ReprEntryNative, ReprFileLocation

from .utils import number_of_working_processes, get_n_proc_for_test, mark_skip, add_n_procs

#from more_itertools import partition
import numpy as np
from bisect import bisect_left

def gather_report(mpi_reports, n_sub_rank):
  assert len(mpi_reports) == n_sub_rank

  report_init = mpi_reports[0]
  goutcome = report_init.outcome
  glongrepr = report_init.longrepr

  collect_longrepr = []
  # > We need to rebuild a TestReport object, location can be false # TODO ?
  for i_sub_rank, test_report in enumerate(mpi_reports):

    if test_report.outcome == 'failed':
      goutcome = 'failed'

    if test_report.longrepr:
      msg = f'On rank {i_sub_rank} of {n_sub_rank}'
      full_msg = f'\n-------------------------------- {msg} --------------------------------'
      fake_trace_back = ReprTraceback([ReprEntryNative(full_msg)], None, None)
      collect_longrepr.append((fake_trace_back     , ReprFileLocation(*report_init.location), None))
      collect_longrepr.append((test_report.longrepr, ReprFileLocation(*report_init.location), None))

  if len(collect_longrepr) > 0:
    glongrepr = ExceptionChainRepr(collect_longrepr)

  return goutcome, glongrepr


class MPIReporter(object):
  @pytest.hookimpl(hookwrapper=True)
  def pytest_runtest_makereport(self, item):
    """
      Need to hook to pass the test sub-comm to `pytest_runtest_logreport`,
      and for that we add the sub-comm to the only argument of `pytest_runtest_logreport`, that is, `report`
    """
    result = yield
    report = result.get_result()
    report._sub_comm = item._sub_comm

  def _runtest_logreport(self, report):
    """
      Gather reports from all procs participating in the test on rank 0 of the sub_comm
    """
    sub_comm = report._sub_comm
    del report._sub_comm # No need to keep it in the report
                         # Furthermore we need to serialize the report
                         # and mpi4py does not know how to serialize report._sub_comm
    i_sub_rank = sub_comm.Get_rank()
    n_sub_rank = sub_comm.Get_size()

    if report.outcome != 'skipped': # Skipped test are only known by proc 0 -> no merge required
      # Warning: PyTest reports can actually be quite big
      request = sub_comm.isend(report, dest=0, tag=i_sub_rank)

      if i_sub_rank == 0:
        mpi_reports = n_sub_rank * [None]
        for _ in range(n_sub_rank):
          status = MPI.Status()

          mpi_report = sub_comm.recv(source=MPI.ANY_SOURCE, tag=MPI.ANY_TAG, status=status)
          mpi_reports[status.Get_source()] = mpi_report

        assert None not in mpi_reports # should have received from all ranks of `sub_comm`
        goutcome, glongrepr = gather_report(mpi_reports, n_sub_rank)

        # report.location = report_gather.location# TODO
        report.outcome  = goutcome
        report.longrepr = glongrepr
      #else:
      #  # report.location = # TODO
      #  # report.outcome  = # TODO gather from 0
      #  report.longrepr = None

      request.wait()




def filter_and_add_sub_comm(items, global_comm):
  i_rank    = global_comm.Get_rank()
  n_workers = global_comm.Get_size()

  filtered_items = []
  for item in items:
    n_proc_test = get_n_proc_for_test(item)

    if n_proc_test > n_workers: # not enough procs: will be skipped
      if global_comm.Get_rank() == 0:
        item._sub_comm = MPI.COMM_SELF
        mark_skip(item)
        filtered_items += [item]
      else:
        item._sub_comm = MPI.COMM_NULL
    else:
      if i_rank < n_proc_test:
        color = 1
      else:
        color = MPI.UNDEFINED

      sub_comm = global_comm.Split(color)

      if sub_comm != MPI.COMM_NULL:
        item._sub_comm = sub_comm
        filtered_items += [item]

  return filtered_items


class SequentialScheduler(MPIReporter):
  def __init__(self, global_comm):
    self.global_comm = global_comm

  @pytest.mark.trylast
  def pytest_collection_modifyitems(self, config, items):
    items[:] = filter_and_add_sub_comm(items, self.global_comm)

  @pytest.mark.tryfirst
  def pytest_runtest_logreport(self, report):
    self._runtest_logreport(report)





def group_items_by_parallel_steps(items, n_workers):
  add_n_procs(items)
  items.sort(key=lambda item: item._n_mpi_proc, reverse=True)

  remaining_n_procs_by_step = []
  items_by_step = []
  items_to_skip = []
  for item in items:
    if item._n_mpi_proc > n_workers:
      items_to_skip += [item]
    else:
      found_step = False
      for i in range(len(remaining_n_procs_by_step)):
        if item._n_mpi_proc <= remaining_n_procs_by_step[i]:
          items_by_step[i] += [item]
          remaining_n_procs_by_step[i] -= item._n_mpi_proc
          found_step = True
          break
      if not found_step:
        items_by_step += [[item]]
        remaining_n_procs_by_step += [n_workers - item._n_mpi_proc]

  return items_by_step, items_to_skip

def run_item_test(item, nextitem, session):
  item.config.hook.pytest_runtest_protocol(item=item, nextitem=nextitem)
  if session.shouldfail:
      raise session.Failed(session.shouldfail)
  if session.shouldstop:
      raise session.Interrupted(session.shouldstop)

def prepare_items_to_run(items, comm):
  n_rank = comm.Get_size()
  i_rank = comm.Get_rank()

  items_to_run = [] 

  beg_next_rank = 0
  for item in items:
    n_proc_test = get_n_proc_for_test(item)

    if beg_next_rank <= i_rank and i_rank < beg_next_rank+n_proc_test :
      color = 1
      items_to_run += [item]    
    else:
      color = MPI.UNDEFINED

    comm_split = comm.Split(color)

    item._sub_comm = comm_split
    item._master_running_proc = beg_next_rank
    item._run_on_this_proc = True

    # even for test not run on rank 0, the test must be seen by PyTest 
    if i_rank==0 and item._sub_comm == MPI.COMM_NULL:
      items_to_run += [item]    
      item._sub_comm = MPI.COMM_SELF
      item._run_on_this_proc = False

    beg_next_rank += n_proc_test

  return items_to_run

def items_to_run_on_this_proc(items_by_steps, items_to_skip, comm):
  i_rank = comm.Get_rank()

  items = []

  # on rank 0, mark items to skip because not enough procs
  if i_rank == 0:
    for item in items_to_skip:
      item._sub_comm = MPI.COMM_SELF
      item._master_running_proc = i_rank
      item._run_on_this_proc = True
      mark_skip(item)
    items += items_to_skip

  # distribute items that will really be run
  for items_of_step in items_by_steps:
    items += prepare_items_to_run(items_of_step, comm)

  return items

class StaticScheduler(MPIReporter):
  def __init__(self, global_comm):
    self.global_comm = global_comm

  @pytest.hookimpl(hookwrapper=True)
  def pytest_runtest_makereport(self, item):
    """
      Need to hook to pass the test sub-comm and the master_running_proc to `pytest_runtest_logreport`,
      and for that we add the sub-comm to the only argument of `pytest_runtest_logreport`, that is, `report`
      Also, tf test is not run on this proc, mark the outcome accordingly
    """
    result = yield
    report = result.get_result()
    report._sub_comm = item._sub_comm
    report._master_running_proc = item._master_running_proc
    if not item._run_on_this_proc:
      report.outcome = 'not_run_on_this_proc'

  @pytest.mark.tryfirst
  def pytest_runtest_logreport(self, report):
    sub_comm = report._sub_comm
    self._runtest_logreport(report)

    # master ranks of each sub_comm must send their report to rank 0
    if sub_comm.Get_rank() == 0:
      if self.global_comm.Get_rank() != 0:
        self.global_comm.send(report, dest=0)
      elif report._master_running_proc != 0:
        mpi_report = self.global_comm.recv(source=report._master_running_proc, tag=MPI.ANY_TAG)

        report.outcome  = mpi_report.outcome
        report.longrepr = mpi_report.longrepr

  @pytest.mark.tryfirst
  def pytest_runtestloop(self, session) -> bool:
    if session.testsfailed and not session.config.option.continue_on_collection_errors:
      raise session.Interrupted(
        "%d error%s during collection"
        % (session.testsfailed, "s" if session.testsfailed != 1 else "")
      )

    if session.config.option.collectonly:
      return True

    n_workers = self.global_comm.Get_size()

    items_by_steps, items_to_skip = group_items_by_parallel_steps(session.items, n_workers)

    items = items_to_run_on_this_proc(items_by_steps, items_to_skip, self.global_comm)

    for i, item in enumerate(items):
      nextitem = items[i + 1] if i + 1 < len(items) else None
      run_item_test(item, nextitem, session)
    return True







#def run_item_test(item, session):
#  nextitem = None # not known at this point
#  item.config.hook.pytest_runtest_protocol(item=item, nextitem=nextitem)
#  if session.shouldfail:
#    raise session.Failed(session.shouldfail)
#  if session.shouldstop:
#    raise session.Interrupted(session.shouldstop)
#
#
#def sub_comm_from_ranks(global_comm, sub_ranks):
#  group = global_comm.group()
#  sub_group = group.Incl(sub_ranks)
#  sub_comm = global_comm.Create_group(sub_group)
#  return sub_comm
#
## TODO bisect_left with key arg only available in Python 3.10
#def bisect_left(a, x, lo=0, hi=None, *, key=None):
#    if lo < 0:
#        raise ValueError('lo must be non-negative')
#    if hi is None:
#        hi = len(a)
#    # Note, the comparison uses "<" to match the
#    # __lt__() logic in list.sort() and in heapq.
#    if key is None:
#        while lo < hi:
#            mid = (lo + hi) // 2
#            if a[mid] < x:
#                lo = mid + 1
#            else:
#                hi = mid
#    else:
#        while lo < hi:
#            mid = (lo + hi) // 2
#            if key(a[mid]) < x:
#                lo = mid + 1
#            else:
#                hi = mid
#    return lo
#
#def item_with_biggest_admissible_n_proc(
#  return = bisect_left(items_to_run, n_av_procs, key=lambda item: item._n_mpi_proc)
#
#class DynamicScheduler(MPIReporter):
#  def __init__(self, global_comm, inter_comm):
#    self.global_comm = global_comm
#    self.inter_comm = inter_comm
#
#  @pytest.mark.tryfirst
#  def pytest_runtestloop(self, session) -> bool:
#    if session.testsfailed and not session.config.option.continue_on_collection_errors:
#      raise session.Interrupted(
#        "%d error%s during collection"
#        % (session.testsfailed, "s" if session.testsfailed != 1 else "")
#      )
#
#    if session.config.option.collectonly:
#      return True
#
#  # parallel algo begin
#    n_workers = number_of_working_processes(comm)
#
#    # add proc to items
#    add_n_procs(session.items)
#
#    # isolate skips
#    has_enough_procs = lambda item: item._n_mpi_proc <= n_workers
#    items_to_skip, items_to_run = partition(has_enough_procs, session.items)
#
#    # mark and run skip
#    for item in items_to_skip:
#      mark_skip(item)
#      run_item_test(item, session)
#
#    items_to_run = sorted(items_to_run, key=lambda item: item._n_mpi_proc)
#    available_procs = np.ones(n_workers, dtype=np.int8)
#
#    while len(items_to_run) > 0:
#      n_av_procs = np.sum(available_procs)
#
#      item = item_with_biggest_admissible_n_proc(items_to_run, n_av_procs)
#
#      
#
#
#    sub_comm_from_ranks(global_comm, sub_ranks)
#
#    for item in items:
#      run_item_test(item, session)
#    return True
