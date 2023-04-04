import pytest

from mpi4py import MPI
import numpy as np

from _pytest.reports import TestReport
from _pytest._code.code import ExceptionChainRepr, ReprTraceback, ReprEntry, ReprEntryNative, ReprFileLocation

from _pytest.terminal import TerminalReporter #TODO DEL


def gather_report(mpi_reports, sub_comm, global_comm):
  assert len(mpi_reports) == sub_comm.Get_size()

  report_init = mpi_reports[0]
  goutcome = report_init.outcome
  glongrepr = report_init.longrepr

  collect_longrepr = []
  # > We need to rebuild a TestReport object, location can be false
  # > Report appears in rank increasing order
  if goutcome != 'skipped':
    # Skipped test are only know by proc 0 -> no merge required
    for test_report in mpi_reports:

      if test_report.outcome == 'failed':
        goutcome = test_report.outcome

      #print('test_report.longrepr = ||',test_report.longrepr,30*'|=')

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
  __slots__ = ['global_comm']
  def __init__(self, global_comm):
    self.global_comm = global_comm


  @pytest.hookimpl(hookwrapper=True)
  def pytest_runtest_makereport(self, item):
    """
      Need to hook to pass the test sub-comm to `pytest_runtest_logreport`,
      and for that we add the sub-comm to the only argument of `pytest_runtest_logreport`, that is, `report`
    """
    print('START pytest_runtest_makereport')
    outcome = yield
    report = outcome.get_result()
    report._sub_comm = item._sub_comm
    print('END pytest_runtest_makereport')

  @pytest.mark.tryfirst
  def pytest_runtest_logreport(self, report):
    """
    """
    print('START pytest_runtest_logreport')
    sub_comm = report._sub_comm
    del report._sub_comm

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
    print('END pytest_runtest_logreport')

  @pytest.hookimpl(hookwrapper=True, tryfirst=True)
  def pytest_terminal_summary(self):
    print('START pytest_terminal_summary')
    outcome = yield
    print('END pytest_terminal_summary')

  #@pytest.hookimpl(hookwrapper=True)
  #def pytest_terminal_summary(self):
  #  self.summary_errors()
  #  self.summary_failures()
  #  self.summary_warnings()
  #  self.summary_passes()
  #  yield
  #  self.short_test_summary()
  #  # Display any extra warnings from teardown here (if any).
  #  self.summary_warnings()

  #@pytest.hookimpl(hookwrapper=True, trylast=True)
  #def pytest_sessionfinish(self, session):
  #  print('START pytest_sessionfinish')
  #  outcome = yield
  #  report = outcome.get_result()
  #  print('END pytest_sessionfinish')

  #@pytest.mark.tryfirst
  #@pytest.hookimpl(hookwrapper=True)
  #def pytest_sessionfinish(self, session):
  #  """
  #  """
  #  self.global_comm.Barrier()
  #  n_send_tot = self.global_comm.reduce(self.n_send, root=0)


  #  if self.global_comm.Get_rank() == 0:
  #    mpi_reports_by_node_id = defaultdict(list)
  #    for _ in range(n_send_tot):
  #      status = MPI.Status()
  #      # print(dir(status))
  #      is_ok_to_recv = self.global_comm.probe(MPI.ANY_SOURCE, MPI.ANY_TAG, status=status)
  #      if is_ok_to_recv:
  #        report = self.global_comm.recv(source=status.Get_source(), tag=status.Get_tag())
  #        if report:
  #          mpi_reports_by_node_id[report.nodeid].append(MPI_report(status.Get_source(), report))

  #    # > Sort by increasing rank number
  #    for _, mpi_reports  in mpi_reports_by_node_id.items():
  #      mpi_reports.sort(key = lambda mpi_report: mpi_report.source_rank)


  #    reports_gather = gather_reports(mpi_reports_by_node_id, self.global_comm)

  #    mpi_terminal_reporter = session.config.pluginmanager.getplugin('terminalreporter')
  #    for i_report, report in reports_gather.items():
  #      #print(50*'=')
  #      #print(i_report)
  #      #print('report[0] = |',report[0],'|')
  #      TerminalReporter.pytest_runtest_logreport(mpi_terminal_reporter, report[0])

  #  MPI.Request.waitall(self.requests)
