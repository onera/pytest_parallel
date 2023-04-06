import pytest
import sys

from .mark import comm # seems unused, but used by pytest # TODO check

from mpi4py import MPI

from .mpi_reporter import sequential_scheduler, static_scheduler#, dynamic_scheduler

#from .html_mpi     import HTMLReportMPI
#from .junit_mpi    import LogXMLMPI
#from _pytest.junitxml import xml_key

from .utils import spawn_master_process, is_master_process

from _pytest.terminal import TerminalReporter

def pytest_addoption(parser):
  parser.addoption('--scheduler', dest='scheduler', type='choice', choices=['sequential','static','dynamic'], default='sequential')


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

  # only report to terminal if master process
  if not is_master_process(global_comm, scheduler):
    terminal_reporter = config.pluginmanager.getplugin('terminalreporter')
    config.pluginmanager.unregister(terminal_reporter)


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
