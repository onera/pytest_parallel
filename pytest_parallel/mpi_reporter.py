import pytest

from mpi4py import MPI

from _pytest._code.code import ExceptionChainRepr, ReprTraceback, ReprEntry, ReprEntryNative, ReprFileLocation
from _pytest.outcomes import Exit
from _pytest.runner import check_interactive_exception, CallInfo

from .utils import number_of_working_processes, get_n_proc_for_test, mark_skip, add_n_procs, is_dyn_master_process
from .algo import partition, lower_bound
import operator
import numpy as np


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


def gather_report_on_local_rank_0(report):
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

      report.outcome  = goutcome
      report.longrepr = glongrepr

    request.wait()

  sub_comm.barrier()




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
        item._sub_comm = MPI.COMM_NULL # TODO this should not be needed
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


class SequentialScheduler:
  def __init__(self, global_comm):
    self.global_comm = global_comm

  @pytest.mark.trylast
  def pytest_collection_modifyitems(self, config, items):
    items[:] = filter_and_add_sub_comm(items, self.global_comm)

  @pytest.hookimpl(hookwrapper=True, tryfirst=True)
  def pytest_runtestloop(self, session) -> bool:
    outcome = yield

    # prevent return value being non-zero (ExitCode.NO_TESTS_COLLECTED) when no test run on non-master
    if self.global_comm.Get_rank() != 0 and session.testscollected == 0:
      session.testscollected = 1
    return True

  @pytest.hookimpl(hookwrapper=True)
  def pytest_runtest_makereport(self, item):
    """
      Need to hook to pass the test sub-comm to `pytest_runtest_logreport`,
      and for that we add the sub-comm to the only argument of `pytest_runtest_logreport`, that is, `report`
    """
    result = yield
    report = result.get_result()
    report._sub_comm = item._sub_comm

  @pytest.mark.tryfirst
  def pytest_runtest_logreport(self, report):
    gather_report_on_local_rank_0(report)




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

def call_runtest_hook(item, when, cond, **kwds):
  if cond:
    if when == "setup":
        ihook = item.ihook.pytest_runtest_setup
    elif when == "call":
        ihook = item.ihook.pytest_runtest_call
    elif when == "teardown":
        ihook = item.ihook.pytest_runtest_teardown
    else:
        assert False, f"Unhandled runtest hook case: {when}"
  else:
    def noop(*args, **kargs): return None
    ihook = noop
  reraise = (Exit,)
  if not item.config.getoption("usepdb", False):
      reraise += (KeyboardInterrupt,)
  return CallInfo.from_call(
      lambda: ihook(item=item, **kwds), when=when, reraise=reraise
  )
def call_and_report(item, when, cond, log: bool = True, **kwds):
    call = call_runtest_hook(item, when, cond, **kwds)
    hook = item.ihook
    report: TestReport = hook.pytest_runtest_makereport(item=item, call=call)
    if log:
        hook.pytest_runtest_logreport(report=report)
    if check_interactive_exception(call, report):
        hook.pytest_exception_interact(node=item, call=call, report=report)
    return report
def runtestprotocol(item, cond, log: bool = True, nextitem = None):
    hasrequest = hasattr(item, "_request")
    if hasrequest and not item._request:  # type: ignore[attr-defined]
        # This only happens if the item is re-run, as is done by
        # pytest-rerunfailures.
        item._initrequest()  # type: ignore[attr-defined]
    rep = call_and_report(item, "setup", cond, log)
    reports = [rep]
    if rep.passed:
        if item.config.getoption("setupshow", False):
            show_test_item(item)
        if not item.config.getoption("setuponly", False):
            reports.append(call_and_report(item, "call", cond, log))
    reports.append(call_and_report(item, "teardown", cond, log, nextitem=nextitem))
    # After all teardown hooks have been called
    # want funcargs and request info to go away.
    if hasrequest:
        item._request = False  # type: ignore[attr-defined]
        item.funcargs = None  # type: ignore[attr-defined]
    return reports
def runtest_protocol(item, nextitem, cond) -> bool:
    ihook = item.ihook
    ihook.pytest_runtest_logstart(nodeid=item.nodeid, location=item.location)
    runtestprotocol(item, nextitem=nextitem, cond=cond)
    ihook.pytest_runtest_logfinish(nodeid=item.nodeid, location=item.location)
    return True
def run_item_test_with_condition(item, nextitem, session, cond):
  runtest_protocol(item=item, nextitem=nextitem, cond=cond)
  if session.shouldfail:
      raise session.Failed(session.shouldfail)
  if session.shouldstop:
      raise session.Interrupted(session.shouldstop)

def run_item_test_no_hook(item, nextitem, session):
  cond = item._run_on_this_proc
  return run_item_test_with_condition(item, nextitem, session, cond)
def run_item_test_no_hook2(item, nextitem, session, inter_comm):
  cond = not is_dyn_master_process(inter_comm) or (hasattr(item,'_mpi_skip') and item._mpi_skip)
  return run_item_test_with_condition(item, nextitem, session, cond)



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
      item._master_running_proc = 0
      item._run_on_this_proc = True
      mark_skip(item)
    items += items_to_skip

  # distribute items that will really be run
  for items_of_step in items_by_steps:
    items += prepare_items_to_run(items_of_step, comm)

  return items

class StaticScheduler:
  def __init__(self, global_comm):
    self.global_comm = global_comm.Dup() # ensure that all communications within the framework are private to the framework

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
      #nextitem = items[i + 1] if i + 1 < len(items) else None
      # For optimization purposes, it would be nice to have the previous commented line
      # (`nextitem` is only used internally by PyTest in _setupstate.teardown_exact)
      # Here, it does not work:
      #   it seems that things are messed up on rank 0
      #   because the nextitem might not be run (see pytest_runtest_setup/call/teardown hooks just above)
      # In practice though, it seems that it is not the main thing that slows things down...

      nextitem = None
      run_item_test_no_hook(item, nextitem, session)

    # prevent return value being non-zero (ExitCode.NO_TESTS_COLLECTED) when no test run on non-master
    if self.global_comm.Get_rank() != 0 and session.testscollected == 0:
      session.testscollected = 1
    return True

  @pytest.hookimpl(hookwrapper=True)
  def pytest_runtest_makereport(self, item):
    """
      Need to hook to pass the test sub-comm and the master_running_proc to `pytest_runtest_logreport`,
      and for that we add the sub-comm to the only argument of `pytest_runtest_logreport`, that is, `report`
      Also, if test is not run on this proc, mark the outcome accordingly
    """
    result = yield
    report = result.get_result()
    report._sub_comm = item._sub_comm
    report._master_running_proc = item._master_running_proc

  @pytest.mark.tryfirst
  def pytest_runtest_logreport(self, report):
    sub_comm = report._sub_comm
    gather_report_on_local_rank_0(report)

    # master ranks of each sub_comm must send their report to rank 0
    if sub_comm.Get_rank() == 0: # only master are concerned
      if self.global_comm.Get_rank() != 0: # if master is not global master, send
        self.global_comm.send(report, dest=0)
      elif report._master_running_proc != 0: # else, recv if test run remotely
        # In the line below, MPI.ANY_TAG will NOT clash with communications outside the framework because self.global_comm is private
        mpi_report = self.global_comm.recv(source=report._master_running_proc, tag=MPI.ANY_TAG)

        report.outcome  = mpi_report.outcome
        report.longrepr = mpi_report.longrepr




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

  # best choices: tests requiring the most procs while still 'runnable'
  # among those, we favor the first in the array for 'stability' reasons (no reordering when not needed)
  idx = lower_bound(items, n_av_procs, key)
  if idx==0 and items[idx]._n_mpi_proc>n_av_procs: idx = -1 # return -1 if all items ask too much
  if idx==len(items): # more than enough available procs
    # Here items[-1] would be OK, but prefer the first item with the same _n_mpi_procs
    max_needed_n_proc = items[-1]._n_mpi_proc
    idx = lower_bound(items, max_needed_n_proc, key)
  return idx

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

  # the procs are busy
  for sub_rank in sub_ranks:
    available_procs[sub_rank] = False

  # TODO isend would be slightly better (less waiting)
  for sub_rank in sub_ranks:
    inter_comm.send((original_idx,sub_ranks), dest=sub_rank, tag=SCHEDULED_WORK_TAG)

def signal_all_done(inter_comm):
  n_workers = number_of_working_processes(inter_comm)
  for i_rank in range(n_workers):
    inter_comm.send((-1,[]), dest=i_rank, tag=SCHEDULED_WORK_TAG)

def wait_test_to_complete(items_to_run, session, available_procs, inter_comm):
  # receive from any proc
  status = MPI.Status()
  original_idx = inter_comm.recv(source=MPI.ANY_SOURCE, tag=WORK_DONE_TAG, status=status)
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
  nextitem = None # not known at this point
  run_item_test_no_hook2(item, nextitem, session, inter_comm)

def wait_last_tests_to_complete(items_to_run, session, available_procs, inter_comm):
  while np.sum(available_procs) < len(available_procs):
    wait_test_to_complete(items_to_run, session, available_procs, inter_comm)


####### Client #######
def receive_run_and_report_tests(items_to_run, session, current_item_requests, global_comm, inter_comm):
  while True:
    # receive
    original_idx, sub_ranks = inter_comm.recv(source=0, tag=SCHEDULED_WORK_TAG)
    if original_idx == -1: return # signal work is done

    # run
    sub_comm = sub_comm_from_ranks(global_comm, sub_ranks)
    item = items_to_run[original_idx]
    item._sub_comm = sub_comm
    nextitem = None # not known at this point
    run_item_test_no_hook2(item, nextitem, session, inter_comm)

    # signal work is done for the test
    inter_comm.send(original_idx, dest=0, tag=WORK_DONE_TAG)

    MPI.Request.waitall(current_item_requests) # make sure all report isends have been received
    current_item_requests.clear()




class DynamicScheduler:
  def __init__(self, global_comm, inter_comm):
    self.global_comm = global_comm
    self.inter_comm = inter_comm
    self.current_item_requests = []


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

    # parallel algo begin
    n_workers = number_of_working_processes(self.inter_comm)

    ## add proc to items
    add_n_procs(session.items)

    ## isolate skips
    has_enough_procs = lambda item: item._n_mpi_proc <= n_workers
    items_to_run, items_to_skip = partition(session.items, has_enough_procs)

    ## remember original position
    #   since every proc is doing that, the original position is the same for all procs
    #   hence, the position can be sent and received among procs: it will lead to the same item
    mark_original_index(items_to_run)

    ## if master proc, schedule
    if is_dyn_master_process(self.inter_comm):
      # mark and run skipped tests
      for i, item in enumerate(items_to_skip):
        item._sub_comm = MPI.COMM_SELF
        mark_skip(item)
        nextitem = items_to_skip[i + 1] if i + 1 < len(items_to_skip) else None
        run_item_test_no_hook2(item, nextitem, session, self.inter_comm)

      # schedule tests to run
      items_left_to_run = sorted(items_to_run, key=lambda item: item._n_mpi_proc)
      available_procs = np.ones(n_workers, dtype=np.int8)

      while len(items_left_to_run) > 0:
        n_av_procs = np.sum(available_procs)

        item_idx = item_with_biggest_admissible_n_proc(items_left_to_run, n_av_procs)

        if item_idx == -1:
          wait_test_to_complete(items_to_run, session, available_procs, self.inter_comm)
        else:
          schedule_test(items_left_to_run[item_idx], available_procs, self.inter_comm)
          del items_left_to_run[item_idx]

      wait_last_tests_to_complete(items_to_run, session, available_procs, self.inter_comm)
      signal_all_done(self.inter_comm)
    else: ## worker proc
      receive_run_and_report_tests(items_to_run, session, self.current_item_requests, self.global_comm, self.inter_comm)
    return True


  @pytest.hookimpl(hookwrapper=True)
  def pytest_runtest_makereport(self, item):
    """
      Need to hook to pass the test sub-comm and the master_running_proc to `pytest_runtest_logreport`,
      and for that we add the sub-comm to the only argument of `pytest_runtest_logreport`, that is, `report`
      Also, if test is not run on this proc, mark the outcome accordingly
    """
    result = yield
    report = result.get_result()
    if is_dyn_master_process(self.inter_comm):
      if hasattr(item,'_mpi_skip') and item._mpi_skip:
        report._mpi_skip = True
        report._sub_comm = item._sub_comm
      else:
        report._master_running_proc = item._sub_ranks[0]
    else:
      report._sub_comm = item._sub_comm

  @pytest.mark.tryfirst
  def pytest_runtest_logreport(self, report):
    if hasattr(report,'_mpi_skip') and report._mpi_skip:
      gather_report_on_local_rank_0(report) # has been 'run' locally: do nothing special
    else:
      assert report.when == 'setup' or report.when == 'call' or report.when == 'teardown' # only know tags
      tag = WHEN_TAGS[report.when]

      # master ranks of each sub_comm must send their report to rank 0
      if not is_dyn_master_process(self.inter_comm):
        sub_comm = report._sub_comm
        gather_report_on_local_rank_0(report)

        if sub_comm.Get_rank() == 0: # if local master proc, send
          # The idea of the scheduler is the following:
          #   The server schedules test over clients
          #   A client executes the test then report to the server it is done
          #   The server execute the PyTest pipeline to make it think it ran the test (but only receives the reports of the client)
          #   The server continues its scheduling
          # Here in the report, we need an isend, because the ordering is the following:
          #   Client: run test, isend reports, send done to server
          #   Server: recv done from client, 'run' test (i.e. recv reports)
          # So the 'send done' must be received before the 'send report'
          request = self.inter_comm.isend(report, dest=0, tag=tag)
          self.current_item_requests.append(request)
      else: # global master: receive
        mpi_report = self.inter_comm.recv(source=report._master_running_proc, tag=tag)

        report.outcome  = mpi_report.outcome
        report.longrepr = mpi_report.longrepr
