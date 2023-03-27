import pytest
import sys

from .mark import comm # seems unused, but used by pytest # TODO check

from mpi4py import MPI

#from .html_mpi     import HTMLReportMPI
#from .junit_mpi    import LogXMLMPI
from .terminal_reporter_mpi import TerminalReporterMPI
from .mpi_reporter import MPIReporter
#from _pytest.junitxml import xml_key

from .utils import prepare_subcomm_for_tests, filter_items, terminate_with_no_exception

from _pytest.terminal import TerminalReporter

def pytest_addoption(parser):
  parser.addoption('--report-file', dest='report_file', default=None)

# --------------------------------------------------------------------------
@pytest.mark.trylast
def pytest_collection_modifyitems(config, items):
  prepare_subcomm_for_tests(items)
  items[:] = filter_items(items)

# --------------------------------------------------------------------------
@pytest.mark.trylast
def pytest_configure(config):
  comm = MPI.COMM_WORLD
  # 0. Open `report_file` if necessary
  report_file = config.getoption("report_file")

  # TODO change TerminalReporterMPI to not need to do that
  if comm.Get_rank() != 0:
    report_file = f'pytest.{comm.Get_rank()}.log'

  if isinstance(report_file, str):
    try:
      report_file = open(report_file,'w')
    except Exception as e:
      terminate_with_no_exception(str(e))

  config._report_file = report_file # keep a link here so we can close the file in `pytest_unconfigure`

  # 1. Change terminalreporter so it uses TerminalReporterMPI
  mpi_reporter = MPIReporter(comm)
  config.pluginmanager.register(mpi_reporter,'pytest_parallel')

  standard_terminal_reporter = config.pluginmanager.getplugin('terminalreporter')
  config.pluginmanager.unregister(standard_terminal_reporter)

  #mpi_terminal_reporter = TerminalReporterMPI(comm, config, report_file, mpi_reporter)
  mpi_terminal_reporter = TerminalReporterMPI(comm, config, report_file, None)
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
  #    config._html = HTMLReportMPI(comm, htmlpath, config, mpi_reporter)
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
  #        mpi_reporter,
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
  if config._report_file is not None:
    config._report_file.close()
  #html = getattr(config, "_html", None)
  #if html:
  #  del config._html
  #  config.pluginmanager.unregister(html)

  #xml = config._store.get(xml_key, None)
  #if xml:
  #    del config._store[xml_key]
  #    config.pluginmanager.unregister(xml)
