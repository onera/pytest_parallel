# -*- coding: utf-8 -*-

import py
import pytest
from mpi4py import MPI
from _pytest.nodes import Item
from _pytest.terminal import TerminalReporter
from _pytest._code.code import ExceptionChainRepr
from _pytest.reports import TestReport
from _pytest.junitxml import LogXML
import sys
# from . import html_mpi
from mpi4py import MPI
from collections import defaultdict
from _pytest import deprecated
from _pytest.warnings import _issue_warning_captured

from pytest_html.plugin import HTMLReport

# --------------------------------------------------------------------------
class HTMLReportMPI(HTMLReport):
  def __init__(self, comm, htmlpath, config):
    """
    """
    # print("HTMLReportMPI")
    HTMLReport.__init__(self, htmlpath, config)

    self.comm         = comm
    self.mpi_requests = defaultdict(list)
    self.n_send       = 0
    self.mpi_reports  = defaultdict(list)

  def pytest_runtest_logreport(self, report):
    """
    """
    # print("HTMLReportMPI::pytest_runtest_logreport", report.when)

    if(self.comm.Get_rank() != 0):
      # print(dir(self.comm))
      # > Attention report peut être gros (stdout dedans etc ...)
      req = self.comm.isend(report, dest=0, tag=self.n_send)
      self.n_send += 1

      self.mpi_requests[report.nodeid].append(req)
      # print("ooooo", report.nodeid)

    HTMLReport.pytest_runtest_logreport(self, report)

  def pytest_sessionfinish(self, session):
    """
    """
    nb_recv_tot = self.comm.reduce(self.n_send, root=0)
    # print("nb_recv_tot::", nb_recv_tot)

    for test_name, reqs in self.mpi_requests.items():
      for req in reqs:
        # print(" *********************************** WAIT ")
        req.wait()

    # Si rang 0 il faut Probe tout
    # print(self.comm.Iprobe.__doc__)
    # print(dir(self.comm))

    # ooooooooooooooooooooooooooooooooooooooooooooooooooooooo
    if self.comm.Get_rank() == 0:
      for i_msg in range(nb_recv_tot):
        status = MPI.Status()
        # print(dir(status))
        is_ok_to_recv = self.comm.Iprobe(MPI.ANY_SOURCE, MPI.ANY_TAG, status=status)
        if is_ok_to_recv:
          # print("Status :: ", status.Get_source(), status.Get_tag())
          report = self.comm.recv(source=status.Get_source(), tag=status.Get_tag())
          # > On fait un dictionnaire en attendant de faire list + tri indirect
          if report:
            self.mpi_reports[(status.Get_source(),report.nodeid)].append(report)

        # print(i_msg, " --> ", report.longrepr)

    self.comm.Barrier()
    # ooooooooooooooooooooooooooooooooooooooooooooooooooooooo

    # ooooooooooooooooooooooooooooooooooooooooooooooooooooooo
    # > On gather tout
    # Il faut trier d'abord, pour un test la liste des rang.
    # Puis on refait depuis le debut le rapport
    for test_name, test_reports in self.mpi_reports.items():
      # print("test_name::", test_name)
      for test_report in test_reports:
        # print("test_report::", test_report)

        # Seek the current report
        lreports = self.reports[test_name[1]]
        greport = None
        for lreport in lreports:
          # print("test_report.when == ", test_report.when )
          # print("lreport    .when == ", lreport.when )
          if(test_report.when == lreport.when ):
            greport = lreport

        # Il serai préférable de tout refaire :
        # TestReport() ...
        # see junitxml :: filename, lineno, skipreason = report.longrepr

        # > We find out the good report - Append
        if(test_report.longrepr):
          # print("type(test_report.longrepr) :: ", type(test_report.longrepr))
          print("test_report.longrepr :: ", test_report.longrepr)
          # greport.longrepr.addsection(f" rank {test_name[0]}", test_report.longrepr)
          # greport.longrepr.addsection(f" rank {test_name[0]}", "oooo")
          if greport.longrepr and not isinstance(greport.longrepr, tuple):
            greport.longrepr.addsection(f" rank {test_name[0]}", str(test_report.longrepr))
          else:
            greport.longrepr = test_report.longrepr

          if(test_report.outcome == 'failed'):
            # print(type(test_report.longrepr))
            # print(test_report.longrepr.chain[0][1])
            greport.outcome = test_report.outcome
    # ooooooooooooooooooooooooooooooooooooooooooooooooooooooo

    # ooooooooooooooooooooooooooooooooooooooooooooooooooooooo
    # for test_name, test_reports in self.reports.items():
    #   for test_report in test_reports:
    #     if( test_report.longrepr and isinstance(test_report.longrepr, ExceptionChainRepr)):
    #       print("xoxo"*10)
    #       test_report.longrepr.addsection( "titi", "oooooo\n")
    #       test_report.longrepr.addsection( "toto", "iiiiii\n")
    # ooooooooooooooooooooooooooooooooooooooooooooooooooooooo

    # self.reports = defaultdict(list)
    # print("HTMLReportMPI::pytest_sessionfinish")
    HTMLReport.pytest_sessionfinish(self, session)


class Junit(py.xml.Namespace):
    pass

# --------------------------------------------------------------------------
class LogXMLMPI(LogXML):
  def __init__(self,
               comm,
               logfile,
               prefix,
               suite_name="pytest",
               logging="no",
               report_duration="total",
               family="xunit1",
               log_passing_tests=True):
    """
    """
    # print("HTMLReportMPI")
    self.comm = comm
    LogXML.__init__(self, logfile, prefix, suite_name, logging, report_duration, family, log_passing_tests)

    self.comm         = comm
    self.mpi_requests = defaultdict(list)
    self.n_send       = 0
    self.shift        = 1000
    self.mpi_reports  = defaultdict(list)

  def pytest_runtest_logreport(self, report):
    """
    """
    # print("HTMLReportMPI::pytest_runtest_logreport", report.when)

    if(self.comm.Get_rank() != 0):
      # print(dir(self.comm))
      # > Attention report peut être gros (stdout dedans etc ...)
      req = self.comm.isend(report, dest=0, tag=self.shift+self.n_send)
      self.n_send += 1
      # print("Send tag ::", self.shift+self.n_send)

      self.mpi_requests[report.nodeid].append(req)
      # print("ooooo", report.nodeid)

    LogXML.pytest_runtest_logreport(self, report)

  def finalize(self, report):
    """
    Little hack to not dstroy internal map
    """
    # print("LogXMLMPI::finalize")
    pass

  def pytest_sessionfinish(self, session):
    """
    """
    nb_recv_tot = self.comm.reduce(self.n_send, root=0)
    print("nb_recv_tot::", nb_recv_tot)

    for test_name, reqs in self.mpi_requests.items():
      for req in reqs:
        # print(" *********************************** WAIT ")
        req.wait()

    # Si rang 0 il faut Probe tout
    # print(self.comm.Iprobe.__doc__)
    # print(dir(self.comm))

    # ooooooooooooooooooooooooooooooooooooooooooooooooooooooo
    if self.comm.Get_rank() == 0:
      for i_msg in range(nb_recv_tot):
        status = MPI.Status()
        # print(dir(status))
        tag = 1000+i_msg
        is_ok_to_recv = self.comm.Iprobe(MPI.ANY_SOURCE, tag, status=status)
        if is_ok_to_recv:
          # print("[",i_msg, "] - Status :: ", status.Get_source(), status.Get_tag())
          report = self.comm.recv(source=status.Get_source(), tag=status.Get_tag())
          # > On fait un dictionnaire en attendant de faire list + tri indirect
          if report:
            self.mpi_reports[(status.Get_source(),report.nodeid)].append(report)
    # ooooooooooooooooooooooooooooooooooooooooooooooooooooooo

    self.comm.Barrier()
    # ooooooooooooooooooooooooooooooooooooooooooooooooooooooo
    # LogXML.pytest_sessionfinish(self)
    # print("self.node_reporter::" , self.node_reporters)
    # print("self.node_reporters_ordered::" , self.node_reporters_ordered)



    # print("self.node_reporters_ordered::" , self.node_reporters_ordered)
    # return

    # ooooooooooooooooooooooooooooooooooooooooooooooooooooooo
    # > On gather tout
    # Il faut trier d'abord, pour un test la liste des rang.
    # Puis on refait depuis le debut le rapport
    for test_name, test_reports in self.mpi_reports.items():
      # print("test_name::", test_name)
      for test_report in test_reports:
        print("test_report::", test_report.longrepr)

        # Seek the current report
        # print(type(self.node_reporters))
        # print(self.node_reporters)
        lreport = self.node_reporters[(test_name[1], None)]

        # print(type(test_report))

        # greport.append(Junit(lreport.))
        # Il serai préférable de tout refaire :
        # TestReport() ...
        # see junitxml :: filename, lineno, skipreason = report.longrepr

        # > We find out the good report - Append
        if(test_report.longrepr):
          # print("type(test_report.longrepr) :: ", type(test_report.longrepr))
          # print("test_report.longrepr :: ", test_report.longrepr)
          # greport.longrepr.addsection(f" rank {test_name[0]}", test_report.longrepr)
          # greport.longrepr.addsection(f" rank {test_name[0]}", "oooo")
          lreport.append_failure(test_report)
          # print("*****"*100)
          # exit(1)
          # if greport.longrepr:
          #   greport.longrepr.addsection(f" rank {test_name[0]}", str(test_report.longrepr))
          # else:
          #   greport.longrepr = test_report.longrepr

          # if(test_report.outcome == 'failed'):
          #   # print(type(test_report.longrepr))
          #   # print(test_report.longrepr.chain[0][1])
          #   greport.outcome = test_report.outcome
    # ooooooooooooooooooooooooooooooooooooooooooooooooooooooo

    # ooooooooooooooooooooooooooooooooooooooooooooooooooooooo
    # for test_name, test_reports in self.reports.items():
    #   for test_report in test_reports:
    #     if( test_report.longrepr and isinstance(test_report.longrepr, ExceptionChainRepr)):
    #       print("xoxo"*10)
    #       test_report.longrepr.addsection( "titi", "oooooo\n")
    #       test_report.longrepr.addsection( "toto", "iiiiii\n")
    # ooooooooooooooooooooooooooooooooooooooooooooooooooooooo

    # self.reports = defaultdict(list)
    print("LogXMLMPI::pytest_sessionfinish")
    LogXML.pytest_sessionfinish(self)


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
@pytest.fixture
def sub_comm(request):
  """
  Only return a previous MPI Communicator (build at prepare step )
  """
  return request._pyfuncitem._sub_comm

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

    # print("n_proc_test ::", n_proc_test)
    if(beg_next_rank + n_proc_test > n_rank):
      beg_next_rank = 0

    if(n_proc_test > n_rank):
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

# --------------------------------------------------------------------------
@pytest.mark.tryfirst
def pytest_collection_modifyitems(config, items):
  """
  Skip tests depending on what options are chosen
  """
  comm   = MPI.COMM_WORLD
  n_rank = comm.size
  i_rank = comm.rank

  prepare_subcomm_for_tests(items)

  # with_mpi = config.getoption(WITH_MPI_ARG)
  # only_mpi = config.getoption(ONLY_MPI_ARG)
  for item in items:

    n_proc_test = get_n_proc_for_test(item)
    # print("+++++", n_proc_test, item.nodeid)
    if(n_proc_test > n_rank):
      item.add_marker(pytest.mark.skip(reason=f" Not enought rank to execute test [required/available] : {n_proc_test}/{n_rank}"))


@pytest.mark.tryfirst
def pytest_unconfigure(config):
  html = getattr(config, "_html", None)
  if html:
    del config._html
    config.pluginmanager.unregister(html)


# --------------------------------------------------------------------------
@pytest.mark.tryfirst
def pytest_runtestloop(session):
  """
  """
  comm = MPI.COMM_WORLD
  # print("pytest_runtestloop", comm.rank)

  for i, item in enumerate(session.items):
      item.config.hook.pytest_runtest_protocol(item=item, nextitem=None)
      if session.shouldfail:
        raise session.Failed(session.shouldfail)
      if session.shouldstop:
        raise session.Interrupted(session.shouldstop)
  return True


@pytest.mark.trylast
def pytest_configure(config):

  print("pytest_configure::pytest_mpi_check")

  comm = MPI.COMM_WORLD

  # --------------------------------------------------------------------------------
  # Reconfiguration des logs
  if comm.Get_rank() > 0:
    standard_reporter = config.pluginmanager.getplugin('terminalreporter')
    mpi_log = open(f"pytest_{comm.Get_rank()}.log", "w")
    instaprogress_reporter = TerminalReporter(config, file=mpi_log)

    config.pluginmanager.unregister(standard_reporter)
    config.pluginmanager.register(instaprogress_reporter, 'terminalreporter')
  # --------------------------------------------------------------------------------

  # --------------------------------------------------------------------------------
  # Prevent previous load of other pytest_html
  html = getattr(config, "_html", None)
  if html:
    del config._html
    config.pluginmanager.unregister(html)

  htmlpath = config.getoption("htmlpath")
  if htmlpath:
    missing_css_files = []
    for csspath in config.getoption("css"):
      if not os.path.exists(csspath):
        missing_css_files.append(csspath)

    if missing_css_files:
      oserror = (
                 f"Missing CSS file{'s' if len(missing_css_files) > 1 else ''}:"
                 f" {', '.join(missing_css_files)}"
                 )
      raise OSError(oserror)

    if not hasattr(config, "workerinput"):
      # prevent opening htmlpath on worker nodes (xdist)
      config._html = HTMLReportMPI(comm, htmlpath, config)
      config.pluginmanager.register(config._html)
  # --------------------------------------------------------------------------------


  # --------------------------------------------------------------------------------
  # Prevent previous load of other pytest_html
  xml = getattr(config, "_xml", None)
  if xml:
    del config._xml
    config.pluginmanager.unregister(xml)

  xmlpath = config.option.xmlpath
  # prevent opening xmllog on slave nodes (xdist)
  if xmlpath and not hasattr(config, "slaveinput"):
      junit_family = config.getini("junit_family")
      if not junit_family:
          _issue_warning_captured(deprecated.JUNIT_XML_DEFAULT_FAMILY, config.hook, 2)
          junit_family = "xunit1"
      config._xml = LogXMLMPI(
          comm,
          xmlpath,
          config.option.junitprefix,
          config.getini("junit_suite_name"),
          config.getini("junit_logging"),
          config.getini("junit_duration_report"),
          junit_family,
          config.getini("junit_log_passing_tests"),
      )
      config.pluginmanager.register(config._xml)
  # --------------------------------------------------------------------------------
