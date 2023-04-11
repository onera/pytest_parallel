import pytest

from mpi4py import MPI

from _pytest._code.code import ExceptionChainRepr, ReprTraceback, ReprEntry, ReprEntryNative, ReprFileLocation

from .utils import number_of_working_processes, get_n_proc_for_test, mark_skip, add_n_procs, is_dyn_master_process
from .algo import partition, upper_bound
import numpy as np

def print_mpi(inter_comm, *args):
  red     = "\u001b[31m"
  blue    = "\u001b[34m"
  reset   = "\u001b[0m"
  if is_dyn_master_process(inter_comm):
    prefix = red
  else:
    prefix = blue
  print(prefix,*args,reset)

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
      report.outcome = 'not_run_on_this_proc' # makes PyTest NOT run the test on this proc (see _pytest/runner.py/runtestprotocol)

  @pytest.mark.tryfirst
  def pytest_runtest_logreport(self, report):
    sub_comm = report._sub_comm
    self._runtest_logreport(report)

    # master ranks of each sub_comm must send their report to rank 0
    if sub_comm.Get_rank() == 0: # only master are concerned
      if self.global_comm.Get_rank() != 0: # if master is not global master, recv
        self.global_comm.send(report, dest=0)
      elif report._master_running_proc != 0: # else, recv if test run remotely
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







def sub_comm_from_ranks(global_comm, sub_ranks):
  group = global_comm.group
  sub_group = group.Incl(sub_ranks)
  sub_comm = global_comm.Create_group(sub_group)
  return sub_comm


def item_with_biggest_admissible_n_proc(items, n_av_procs):
  key = lambda item: item._n_mpi_proc
  # Preconditions:
  #   sorted(items, key)
  #   len(items)>0

  idx = upper_bound(items, n_av_procs, key)
  return idx-1 # return the one just before asking too much (-1 if all ask too much)

def mark_original_index(items):
  for i, item in enumerate(items):
    item._original_index = i

########### Client/Server ###########
SCHEDULED_WORK_TAG = 0
WORK_DONE_TAG = 1
REPORT_SETUP_TAG = 2
REPORT_RUN_TAG = 3
REPORT_TEARDOWN_TAG = 4
WHEN_TAGS = {'setup':REPORT_SETUP_TAG, 'call':REPORT_RUN_TAG, 'teardown':REPORT_TEARDOWN_TAG}
####### Server #######
def schedule_test(item, available_procs, inter_comm):
  n_procs = item._n_mpi_proc
  original_idx = item._original_index

  sub_ranks = [] 
  i = 0
  while len(sub_ranks) < n_procs:
    if available_procs[i]:
      sub_ranks.append(i)
    i += 1

  item._sub_ranks = sub_ranks
  print_mpi(inter_comm,'sub_ranks = ',sub_ranks)

  # the procs are busy
  for sub_rank in sub_ranks:
    available_procs[sub_rank] = False

  # TODO isend would be slightly better (less waiting)
  print_mpi(inter_comm,'schedule_test before send')
  for sub_rank in sub_ranks:
    inter_comm.send((original_idx,sub_ranks), dest=sub_rank, tag=SCHEDULED_WORK_TAG)
  print_mpi(inter_comm,'schedule_test after send')

def wait_test_to_complete(items_to_run, available_procs, inter_comm):
  # receive from any proc
  status = MPI.Status()
  print_mpi(inter_comm,'wait_test_to_complete before recv')
  original_idx = inter_comm.recv(source=MPI.ANY_SOURCE, tag=WORK_DONE_TAG)
  print_mpi(inter_comm,'wait_test_to_complete after recv')
  first_rank_done = status.Get_source()

  # get associated item
  item = items_to_run[original_idx]
  n_proc = item._n_mpi_proc
  sub_ranks = item._sub_ranks
  assert first_rank_done in sub_ranks

  # receive done message from all other proc associated to the item
  for sub_rank in sub_ranks:
    if sub_rank != first_rank_done:
      rank_original_idx = inter_comm.recv(source=sub_rank, tag=WORK_DONE_TAG)
      assert rank_original_idx == original_idx # sub_rank is supposed to have worked on the same test

  # the procs are now available
  for sub_rank in sub_ranks:
    available_procs[sub_rank] = True

  # "run" the test (i.e. trigger PyTest pipeline but do not really run the code)
  print_mpi(inter_comm,'wait_test_to_complete before run')
  run_item_test(item, nextitem, session)
  print_mpi(inter_comm,'wait_test_to_complete after run')

def wait_last_tests_to_complete(items_to_run, available_procs, inter_comm):
  while np.sum(available_procs) < len(available_procs):
    wait_test_to_complete(items_to_run, available_procs, inter_comm)


####### Client #######
def receive_run_and_report_tests(items_to_run, session, global_comm, inter_comm):
  # receive
  print_mpi(inter_comm,'receive_run_and_report_tests before recv')
  original_idx, sub_ranks = inter_comm.recv(source=0, tag=SCHEDULED_WORK_TAG)
  print_mpi(inter_comm,'receive_run_and_report_tests after recv')

  # run
  sub_comm = sub_comm_from_ranks(global_comm, sub_ranks)
  item = items_to_run[original_idx]
  item._sub_comm = sub_comm
  nextitem = None # not known at this point
  run_item_test(item, nextitem, session)

  print_mpi(inter_comm,'receive_run_and_report_tests before send')
  inter_comm.send(original_idx, dest=0, tag=WORK_DONE_TAG)
  print_mpi(inter_comm,'receive_run_and_report_tests after send')


class DynamicScheduler(MPIReporter):
  def __init__(self, global_comm, inter_comm):
    self.global_comm = global_comm
    self.inter_comm = inter_comm

  @pytest.mark.tryfirst
  def pytest_runtestloop(self, session) -> bool:
  # same begining as PyTest default's
    if session.testsfailed and not session.config.option.continue_on_collection_errors:
      raise session.Interrupted(
        "%d error%s during collection"
        % (session.testsfailed, "s" if session.testsfailed != 1 else "")
      )

    if session.config.option.collectonly:
      return True

    print_mpi(self.inter_comm,'\nBegin loop')

  # parallel algo begin
    n_workers = number_of_working_processes(self.inter_comm)

    # add proc to items
    add_n_procs(session.items)

    # isolate skips
    has_enough_procs = lambda item: item._n_mpi_proc <= n_workers
    items_to_run, items_to_skip = partition(session.items, has_enough_procs)

    if is_dyn_master_process(self.inter_comm):
      # mark and run skipped tests
      for i, item in enumerate(items_to_skip):
        mark_skip(item)
        nextitem = items_to_skip[i + 1] if i + 1 < len(items_to_skip) else None
        run_item_test(item, nextitem, session)

      # schedule tests to run

      ## once tests are run, they will be erased from the list on the master proc
      ## however, we need to keep the original position to send to the other procs
      items_left_to_run = sorted(items_to_run, key=lambda item: item._n_mpi_proc)
      mark_original_index(items_left_to_run)

      available_procs = np.ones(n_workers, dtype=np.int8)

      while len(items_left_to_run) > 0:
        n_av_procs = np.sum(available_procs)

        item_idx = item_with_biggest_admissible_n_proc(items_left_to_run, n_av_procs)

        if item_idx == -1:
          wait_test_to_complete(items_to_run, available_procs, self.inter_comm)
        else:
          schedule_test(items_left_to_run[item_idx], available_procs, self.inter_comm)
          del items_left_to_run[item_idx]

      wait_last_tests_to_complete(items_to_run, available_procs, self.inter_comm)
    else: # worker proc
      receive_run_and_report_tests(items_to_run, session, self.global_comm, self.inter_comm)
    print_mpi(self.inter_comm,'\nEnd loop')

  @pytest.hookimpl(hookwrapper=True)
  def pytest_runtest_makereport(self, item):
    """
      Need to hook to pass the test sub-comm and the master_running_proc to `pytest_runtest_logreport`,
      and for that we add the sub-comm to the only argument of `pytest_runtest_logreport`, that is, `report`
      Also, tf test is not run on this proc, mark the outcome accordingly
    """
    result = yield
    report = result.get_result()
    if is_dyn_master_process(self.inter_comm):
      print_mpi(self.inter_comm,'    is_dyn_master_process')
      report._master_running_proc = item._sub_ranks[0]
      report.outcome = 'only_fake_run_on_master_proc' # makes PyTest NOT run the test on this proc (see _pytest/runner.py/runtestprotocol)
    else:
      print_mpi(self.inter_comm,'    NOT is_dyn_master_process')
      report._sub_comm = item._sub_comm

  @pytest.mark.tryfirst
  def pytest_runtest_logreport(self, report):
    pass
    #self._runtest_logreport(report)

    #assert report.when == 'setup' or report.when == 'call' or report.when == 'teardown' # only know tags
    #tag = WHEN_TAGS[report.when]

    ## master ranks of each sub_comm must send their report to rank 0
    #if not is_dyn_master_process(self.inter_comm):
    #  sub_comm = report._sub_comm
    #  if sub_comm.Get_rank() == 0: # if local master proc, send
    #    self.inter_comm.send(report, dest=0, tag=tag)
    #else: # global master: receive
    #  mpi_report = self.inter_comm.recv(source=report._master_running_proc, tag=tag)

    #  report.outcome  = mpi_report.outcome
    #  report.longrepr = mpi_report.longrepr
