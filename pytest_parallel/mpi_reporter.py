import pytest

from mpi4py import MPI

from _pytest._code.code import ExceptionChainRepr, ReprTraceback, ReprEntry, ReprEntryNative, ReprFileLocation

from .utils import number_of_working_processes, get_n_proc_for_test#, filter_and_add_sub_comm, filter_items

#from more_itertools import partition
import numpy as np
from bisect import bisect_left

def gather_report(mpi_reports, sub_comm, global_comm):
  assert len(mpi_reports) == sub_comm.Get_size()

  report_init = mpi_reports[0]
  goutcome = report_init.outcome
  glongrepr = report_init.longrepr

  collect_longrepr = []
  # > We need to rebuild a TestReport object, location can be false # TODO ?
  for test_report in mpi_reports:

    if test_report.outcome == 'failed':
      goutcome = 'failed'

    if test_report.longrepr:
      msg = f'On local [{sub_comm.Get_rank()}/{sub_comm.Get_size()}] | global [{global_comm.Get_rank()}/{global_comm.Get_size()}]'
      full_msg = f'\n\n----------------------- {msg} ----------------------- \n\n'
      fake_trace_back = ReprTraceback([ReprEntryNative(full_msg)], None, None)
      collect_longrepr.append((fake_trace_back     , ReprFileLocation(*report_init.location), None))
      collect_longrepr.append((test_report.longrepr, ReprFileLocation(*report_init.location), None))

  if len(collect_longrepr) > 0:
    glongrepr = ExceptionChainRepr(collect_longrepr)

  return goutcome, glongrepr


class MPIReporter(object):
  def __init__(self, global_comm):
    self.global_comm = global_comm


  @pytest.hookimpl(hookwrapper=True)
  def pytest_runtest_makereport(self, item):
    """
      Need to hook to pass the test sub-comm to `pytest_runtest_logreport`,
      and for that we add the sub-comm to the only argument of `pytest_runtest_logreport`, that is, `report`
    """
    outcome = yield
    report = outcome.get_result()
    report._sub_comm = item._sub_comm

  @pytest.mark.tryfirst
  def pytest_runtest_logreport(self, report):
    """
    """
    sub_comm = report._sub_comm
    del report._sub_comm # No need to keep it in the report
                         # Furthermore we need to serialize the report
                         # and mpi4py does not know how to serialize report._sub_comm

    if report.outcome != 'skipped': # Skipped test are only known by proc 0 -> no merge required
      # Warning: PyTest reports can actually be quite big
      request = sub_comm.isend(report, dest=0, tag=sub_comm.Get_rank())

      if sub_comm.Get_rank() == 0:
        mpi_reports = sub_comm.Get_size() * [None]
        for _ in range(sub_comm.Get_size()):
          status = MPI.Status()

          mpi_report = sub_comm.recv(source=MPI.ANY_SOURCE, tag=MPI.ANY_TAG, status=status)
          mpi_reports[status.Get_source()] = mpi_report

        assert None not in mpi_reports # should have received from all ranks of `sub_comm`
        goutcome, glongrepr = gather_report(mpi_reports, sub_comm, self.global_comm)

        # report.location = report_gather.location# TODO
        #report.outcome  = goutcome
        report.longrepr = glongrepr
        #report.longrepr = 50*str(self.global_comm.Get_rank())
      else:
        # report.location = # TODO
        # report.outcome  = # TODO gather from 0
        report.longrepr = None

      request.wait()

def filter_and_add_sub_comm(items, global_comm):
  i_rank    = global_comm.Get_rank()
  n_workers = global_comm.Get_size()

  filtered_items = []
  for item in items:
    n_proc_test = get_n_proc_for_test(item)

    if n_proc_test > n_workers: # not enough procs: will be skipped
      if comm.Get_rank() == 0:
        item._sub_comm = MPI.COMM_SELF
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






class sequential_scheduler(MPIReporter):
  def __init__(self, global_comm):
    MPIReporter.__init__(self, global_comm)

  @pytest.mark.trylast
  def pytest_collection_modifyitems(self, config, items):
    items[:] = filter_and_add_sub_comm(items, self.global_comm)






def group_items_by_parallel_steps(items, n_workers):
  add_n_procs(items)
  items.sort(key=lambda item: item._n_mpi_proc, reverse=True)

  remaining_n_procs_by_step = []
  items_by_step = []
  items_to_skip = []
  for item in items:
    if item._n_mpi_proc > n_workers[i]:
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
        remaining_n_procs_by_step += [n_worker - item._n_mpi_proc]

  return items_by_step, items_to_skip


def run_item_test(item, nextitem, session):
  item.config.hook.pytest_runtest_protocol(item=item, nextitem=nextitem)
  if session.shouldfail:
      raise session.Failed(session.shouldfail)
  if session.shouldstop:
      raise session.Interrupted(session.shouldstop)


class static_scheduler(MPIReporter):
  def __init__(self, global_comm):
    MPIReporter.__init__(self, global_comm)
    print('\n\nstatic_scheduler\n\n')

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

    items_by_steps,items_to_skip = group_items_by_parallel_steps(session.items, n_workers)

    for i, item in enumerate(session.items):
      nextitem = session.items[i + 1] if i + 1 < len(session.items) else None
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
#class dynamic_scheduler(MPIReporter):
#  def __init__(self, global_comm, inter_comm):
#    MPIReporter.__init__(self, global_comm)
#    self.inter_comm = inter_comm
#    print('\n\ndynamic_scheduler\n\n')
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
