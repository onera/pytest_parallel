import pytest
import sys

from .mark import comm # seems unused, but used by pytest # TODO check

from mpi4py import MPI

from .mpi_reporter import sequential_scheduler#, static_scheduler, dynamic_scheduler

#from .html_mpi     import HTMLReportMPI
#from .junit_mpi    import LogXMLMPI
#from _pytest.junitxml import xml_key

#from .utils import prepare_subcomm_for_tests, filter_items, terminate_with_no_exception

from _pytest.terminal import TerminalReporter

def pytest_addoption(parser):
  #parser.addoption('--report-file', dest='report_file', default=None)
  parser.addoption('--scheduler', dest='scheduler', type='choice', choices=['sequential','static','dynamic'], default='sequential')

## --------------------------------------------------------------------------
#@pytest.mark.trylast
#def pytest_collection_modifyitems(config, items):
#  prepare_subcomm_for_tests(items)
#  items[:] = filter_items(items)
#  print('len items = ',len(items))

# --------------------------------------------------------------------------
@pytest.mark.trylast
def pytest_configure(config):
  global_comm = MPI.COMM_WORLD

  scheduler = config.getoption('scheduler')
  if scheduler == 'sequential':
    plugin = sequential_scheduler(global_comm)
  elif scheduler == 'static':
    plugin = static_scheduler(global_comm)
  elif scheduler == 'dynamic':
    inter_comm = spawn_master_process(global_comm)
    plugin = dynamic_scheduler(global_comm, inter_comm)
  else:
    assert 0, 'pytest_configure: unknown scheduler' # TODO pytest error reporting

  config.pluginmanager.register(plugin,'pytest_parallel')

  ## 0. Open `report_file` if necessary
  #report_file = config.getoption("report_file")

  # TODO make `pytest_terminal_summary` do nothing on rank!=0 (hook with non-None result?)
  if global_comm.Get_rank() == 0:
  #parent_comm = global_comm.Get_parent();
  #if parent_comm != MPI.COMM_NULL:
    report_file = None
  else:
    report_file = f'pytest.{global_comm.Get_rank()}.log'

  if isinstance(report_file, str):
    try:
      report_file = open(report_file,'w')
    except Exception as e:
      terminate_with_no_exception(str(e)) # TODO use Pytest terminate mecha

  terminal_reporter = config.pluginmanager.getplugin('terminalreporter')
  config.pluginmanager.unregister(terminal_reporter)
  terminal_reporter= TerminalReporter(config, report_file)
  config.pluginmanager.register(terminal_reporter,'terminalreporter')

  #config._report_file = report_file # keep a link here so we can close the file in `pytest_unconfigure`


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
  #    config._html = HTMLReportMPI(comm, htmlpath, config, plugin)
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
  #        plugin,
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

## --------------------------------------------------------------------------
#@pytest.mark.trylast
#def pytest_unconfigure(config):
#  if config._report_file is not None:
#    config._report_file.close()
#
#  #html = getattr(config, "_html", None)
#  #if html:
#  #  del config._html
#  #  config.pluginmanager.unregister(html)
#
#  #xml = config._store.get(xml_key, None)
#  #if xml:
#  #    del config._store[xml_key]
#  #    config.pluginmanager.unregister(xml)
#
#@pytest.hookimpl(hookwrapper=True, tryfirst=True)
#def pytest_sessionfinish(session):
#  print('START plugin pytest_sessionfinish')
#  outcome = yield
#  print('END plugin pytest_sessionfinish')
