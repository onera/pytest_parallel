import pytest
import sys

from ._decorator import sub_comm

from mpi4py import MPI

from .html_mpi     import HTMLReportMPI
from .junit_mpi    import LogXMLMPI
from .terminal_mpi import TerminalReporterMPI
from .mpi_reporter import MPIReporter
from _pytest.junitxml import xml_key

from .utils import get_n_proc_for_test, prepare_subcomm_for_tests

from _pytest          import deprecated
from _pytest          import runner

from _pytest._code.code import ExceptionChainRepr
from _pytest.terminal   import TerminalReporter

# --------------------------------------------------------------------------
# def pytest_addoption(parser):
#   group = parser.getgroup('mpi-check')
#   group.addoption(
#                   '--foo',
#                   action='store',
#                   dest='dest_foo',
#                   default='2020',
#                   help='Set the value for the fixture "bar".'
#                   )
#   parser.addini('HELLO', 'Dummy pytest.ini setting')

# --------------------------------------------------------------------------
@pytest.mark.trylast
def pytest_collection_modifyitems(config, items):
  """
  Skip tests depending on what options are chosen
  """
  comm   = MPI.COMM_WORLD
  n_rank = comm.size
  i_rank = comm.rank

  # > This fonction do a kind of sheduling because if comm is null the test is not executed
  prepare_subcomm_for_tests(items)

  # Rajouter nombre proc max dans les infos
  filtered_list = []
  # deselected = []
  for item in items:

    n_proc_test = get_n_proc_for_test(item)

    if(n_proc_test > n_rank):
      # assert False, item.nodeid
      item.add_marker(pytest.mark.skip(reason=f" Not enought rank to execute test [required/available] : {n_proc_test}/{n_rank}", append=False))
      filtered_list.append(item)

    if(item._sub_comm != MPI.COMM_NULL):
      filtered_list.append(item)

  # config.hook.pytest_deselected(items=deselected)
  items[:] = filtered_list

  # items[:] = filtered_list # [:] is mandatory because many reference inside pytest

# --------------------------------------------------------------------------
@pytest.mark.trylast
def pytest_configure(config):

  comm = MPI.COMM_WORLD

  # --------------------------------------------------------------------------------
  mpi_reporter = getattr(config, "_mpi_reporter", None)
  if mpi_reporter:
    del config._mpi_reporter
    config.pluginmanager.unregister(mpi_reporter)

  # prevent opening mpi_reporterpath on worker nodes (xdist)
  config._mpi_reporter = MPIReporter(comm)
  config.pluginmanager.register(config._mpi_reporter)
  # --------------------------------------------------------------------------------

  # --------------------------------------------------------------------------------
  # Reconfiguration des logs
  standard_reporter = config.pluginmanager.getplugin('terminalreporter')
  if comm.Get_rank() == 0:
    mpi_log = sys.stdout
  else:
    mpi_log = open(f"pytest_{comm.Get_rank()}.log", "w")
  config._mpi_log = mpi_log
  instaprogress_reporter = TerminalReporterMPI(comm, config, mpi_log, config._mpi_reporter)

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
      config._html = HTMLReportMPI(comm, htmlpath, config, config._mpi_reporter)
      config.pluginmanager.register(config._html)
  # --------------------------------------------------------------------------------

  # --------------------------------------------------------------------------------
  # Prevent previous load of other pytest_html
  xml = config._store.get(xml_key, None)
  if xml:
      del config._store[xml_key]
      config.pluginmanager.unregister(xml)

  xmlpath = config.option.xmlpath
  # Prevent opening xmllog on worker nodes (xdist).
  if xmlpath and not hasattr(config, "workerinput"):
      junit_family = config.getini("junit_family")
      config._store[xml_key] = LogXMLMPI(
          comm,
          config._mpi_reporter,
          xmlpath,
          config.option.junitprefix,
          config.getini("junit_suite_name"),
          config.getini("junit_logging"),
          config.getini("junit_duration_report"),
          junit_family,
          config.getini("junit_log_passing_tests"),
      )
      config.pluginmanager.register(config._store[xml_key])
  # --------------------------------------------------------------------------------

# --------------------------------------------------------------------------
@pytest.mark.trylast
def pytest_unconfigure(config):
  html = getattr(config, "_html", None)
  if html:
    del config._html
    config.pluginmanager.unregister(html)

  xml = config._store.get(xml_key, None)
  if xml:
      del config._store[xml_key]
      config.pluginmanager.unregister(xml)

  _mpi_log = getattr(config, "_mpi_log", None)
  if _mpi_log:
    _mpi_log.close()

@pytest.mark.tryfirst
def pytest_sessionfinish(session, exitstatus):
  standard_reporter = session.config.pluginmanager.getplugin('terminalreporter')
  assert(isinstance(standard_reporter, TerminalReporterMPI))

  # if(not standard_reporter.mpi_reporter.post_done):
  #   standard_reporter.mpi_reporter.pytest_sessionfinish(session)
  assert(standard_reporter.mpi_reporter.post_done == True)

  for i_report, report in standard_reporter.mpi_reporter.reports_gather.items():
    # print(" \n ", i_report, " 2/ ---> ", report, "\n")
    TerminalReporter.pytest_runtest_logreport(standard_reporter, report[0])


