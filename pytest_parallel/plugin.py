import pytest
import sys

from .mark import comm # seems unused, but used by pytest

from mpi4py import MPI

#from .html_mpi     import HTMLReportMPI
#from .junit_mpi    import LogXMLMPI
from .terminal_reporter_mpi import TerminalReporterMPI
from .mpi_reporter import MPIReporter
#from _pytest.junitxml import xml_key

from .utils import get_n_proc_for_test, prepare_subcomm_for_tests, terminate_with_no_exception

from _pytest.terminal   import TerminalReporter

def pytest_addoption(parser):
  parser.addoption('--report-file', dest='report_file', default=None)

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

  filtered_list = []
  for item in items:
    n_proc_test = get_n_proc_for_test(item)

    if n_proc_test > n_rank:
      skip_msg = f'Not enought rank to execute test: {n_proc_test} procs required but only {n_rank} available'
      item.add_marker(pytest.mark.skip(reason=skip_msg, append=False))
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

  config._mpi_reporter = MPIReporter(MPI.COMM_WORLD)
  config.pluginmanager.register(config._mpi_reporter)
  
  # Change terminalreporter so it uses TerminalReporterMPI
  standard_terminal_reporter = config.pluginmanager.getplugin('terminalreporter')
  config.pluginmanager.unregister(standard_terminal_reporter)

  report_file = config.getoption("report_file")
  if isinstance(report_file, str):
    try:
      config._report_file = open(report_file,'w')
    except Exception as e:
      terminate_with_no_exception(str(e))

  mpi_terminal_reporter = TerminalReporterMPI(comm, config, report_file, config._mpi_reporter)
  config.pluginmanager.register(mpi_terminal_reporter, 'terminalreporter')

  ## --------------------------------------------------------------------------------
  ## Prevent previous load of other pytest_html
  #html = getattr(config, "_html", None)
  #if html:
  #  del config._html
  #  config.pluginmanager.unregister(html)

  #htmlpath = config.getoption("htmlpath")
  #if htmlpath:
  #  missing_css_files = []
  #  for csspath in config.getoption("css"):
  #    if not os.path.exists(csspath):
  #      missing_css_files.append(csspath)

  #  if missing_css_files:
  #    oserror = (
  #               f"Missing CSS file{'s' if len(missing_css_files) > 1 else ''}:"
  #               f" {', '.join(missing_css_files)}"
  #               )
  #    raise OSError(oserror)

  #  if not hasattr(config, "workerinput"):
  #    # prevent opening htmlpath on worker nodes (xdist)
  #    config._html = HTMLReportMPI(comm, htmlpath, config, config._mpi_reporter)
  #    config.pluginmanager.register(config._html)
  ## --------------------------------------------------------------------------------

  ## --------------------------------------------------------------------------------
  ## Prevent previous load of other pytest_html
  #xml = config._store.get(xml_key, None)
  #if xml:
  #    del config._store[xml_key]
  #    config.pluginmanager.unregister(xml)

  #xmlpath = config.option.xmlpath
  ## Prevent opening xmllog on worker nodes (xdist).
  #if xmlpath and not hasattr(config, "workerinput"):
  #    junit_family = config.getini("junit_family")
  #    config._store[xml_key] = LogXMLMPI(
  #        comm,
  #        config._mpi_reporter,
  #        xmlpath,
  #        config.option.junitprefix,
  #        config.getini("junit_suite_name"),
  #        config.getini("junit_logging"),
  #        config.getini("junit_duration_report"),
  #        junit_family,
  #        config.getini("junit_log_passing_tests"),
  #    )
  #    config.pluginmanager.register(config._store[xml_key])
  ## --------------------------------------------------------------------------------

# --------------------------------------------------------------------------
@pytest.mark.trylast
def pytest_unconfigure(config):
  pass
  #html = getattr(config, "_html", None)
  #if html:
  #  del config._html
  #  config.pluginmanager.unregister(html)

  #xml = config._store.get(xml_key, None)
  #if xml:
  #    del config._store[xml_key]
  #    config.pluginmanager.unregister(xml)

@pytest.mark.tryfirst
def pytest_sessionfinish(session, exitstatus):
  mpi_terminal_reporter = session.config.pluginmanager.getplugin('terminalreporter')

  if not isinstance(mpi_terminal_reporter, TerminalReporterMPI):
    terminate_with_no_exception('pytest_parallel.pytest_sessionfinish: the "terminalreporter" must be of type "TerminalReporterMPI"')

  if not mpi_terminal_reporter.mpi_reporter.post_done:
    terminate_with_no_exception('pytest_parallel.pytest_sessionfinish: the "terminalreporter" have its attribute "post_done" set to True')

  # TODO
  for i_report, report in mpi_terminal_reporter.mpi_reporter.reports_gather.items():
    TerminalReporter.pytest_runtest_logreport(mpi_terminal_reporter, report[0])
