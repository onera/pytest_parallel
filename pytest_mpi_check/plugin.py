import pytest

from ._decorator import sub_comm

from mpi4py import MPI

from .html_mpi     import HTMLReportMPI
from .junit_mpi    import LogXMLMPI
from .mpi_reporter import MPIReporter

from .utils import get_n_proc_for_test, prepare_subcomm_for_tests

from _pytest          import deprecated
from _pytest.warnings import _issue_warning_captured

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
@pytest.mark.tryfirst
def pytest_collection_modifyitems(config, items):
  """
  Skip tests depending on what options are chosen
  """
  comm   = MPI.COMM_WORLD
  n_rank = comm.size
  i_rank = comm.rank

  # > This fonction do a kind of sheduling because if comm is null the test is not executed
  prepare_subcomm_for_tests(items)

  # with_mpi = config.getoption(WITH_MPI_ARG)
  # only_mpi = config.getoption(ONLY_MPI_ARG)
  # Rajouter nombre proc max dans les infos
  for item in items:

    n_proc_test = get_n_proc_for_test(item)
    # print("+++++", n_proc_test, item.nodeid)
    if(n_proc_test > n_rank):
      item.add_marker(pytest.mark.skip(reason=f" Not enought rank to execute test [required/available] : {n_proc_test}/{n_rank}"))

# --------------------------------------------------------------------------
# @pytest.mark.tryfirst
# def pytest_runtestloop(session):
#   """
#   """
#   comm = MPI.COMM_WORLD
#   # print("pytest_runtestloop", comm.rank)

#   for i, item in enumerate(session.items):
#       item.config.hook.pytest_runtest_protocol(item=item, nextitem=None)
#       if session.shouldfail:
#         raise session.Failed(session.shouldfail)
#       if session.shouldstop:
#         raise session.Interrupted(session.shouldstop)
#   return True

# --------------------------------------------------------------------------
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
  mpi_reporter = getattr(config, "_mpi_reporter", None)
  if mpi_reporter:
    del config._mpi_reporter
    config.pluginmanager.unregister(mpi_reporter)

  # prevent opening mpi_reporterpath on worker nodes (xdist)
  config._mpi_reporter = MPIReporter(comm)
  config.pluginmanager.register(config._mpi_reporter)
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
  xml = getattr(config, "_xml", None)
  if xml:
    del config._xml
    config.pluginmanager.unregister(xml)

  xmlpath = config.option.xmlpath
  # prevent opening xmllog on slave nodes (xdist)
  if xmlpath and not hasattr(config, "slaveinput"):
      junit_family = config.getini("junit_family")
      junit_family = "xunit2"
      if not junit_family:
          _issue_warning_captured(deprecated.JUNIT_XML_DEFAULT_FAMILY, config.hook, 2)
      _issue_warning_captured(deprecated.JUNIT_XML_DEFAULT_FAMILY, config.hook, 2)
      config._xml = LogXMLMPI(
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
      config.pluginmanager.register(config._xml)
  # --------------------------------------------------------------------------------

# --------------------------------------------------------------------------
@pytest.mark.tryfirst
def pytest_unconfigure(config):
  html = getattr(config, "_html", None)
  if html:
    del config._html
    config.pluginmanager.unregister(html)

  xml = getattr(config, "_xml", None)
  if xml:
    del config._xml
    config.pluginmanager.unregister(xml)
