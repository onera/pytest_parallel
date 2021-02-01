# -*- coding: utf-8 -*-

import pytest
from mpi4py import MPI
from _pytest.nodes import Item
from _pytest._code.code import ExceptionChainRepr
import sys
# from . import html_mpi
from mpi4py import MPI
from collections import defaultdict

from pytest_html.plugin import HTMLReport

# --------------------------------------------------------------------------
class HTMLReportMPI(HTMLReport):
  def __init__(self, comm, htmlpath, config):
    """
    """
    print("HTMLReportMPI")
    HTMLReport.__init__(self, htmlpath, config)

    self.comm = comm

  def pytest_runtest_logreport(self, report):
    """
    """
    print("HTMLReportMPI::pytest_runtest_logreport")
    HTMLReport.pytest_runtest_logreport(self, report)

  def pytest_sessionfinish(self, session):
    """
    """

    for test_name, test_reports in self.reports.items():
      for test_report in test_reports:
        if( test_report.longrepr and isinstance(test_report.longrepr, ExceptionChainRepr)):
          print("xoxo"*10)
          test_report.longrepr.addsection( "titi", "oooooo\n")
          test_report.longrepr.addsection( "toto", "iiiiii\n")


    # self.reports = defaultdict(list)
    print("HTMLReportMPI::pytest_sessionfinish")
    HTMLReport.pytest_sessionfinish(self, session)




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
# @pytest.fixture
# def sub_comm(request):
#   """
#   Method for create the sub communicator associate with a test
#   This method cannot work if the scheduler is a priori
#   """
#   # return request._pyfuncitem._sub_comm
#   print("Create sub_comm for each test ")
#   comm = MPI.COMM_WORLD

#   n_proc = request.param

#   # Groups communicator creation
#   gprocs   = [i for i in range(n_proc)]
#   group    = comm.Get_group()
#   subgroup = group.Incl(gprocs)
#   subcomm  = comm.Create(subgroup)

#   # comm.Barrier()

#   return subcomm

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
  # print("*"*100)
  # print(dir(html))
  # print("*"*100)
  # print(html.reports)
  # for nodeid, res in html.reports.items():
  #   print("res::", dir(res))

  # print("x"*100)
  # for test_name, test_reports in html.reports.items():
  #   print("pytest_unconfigure ----> ", test_name, len(test_reports))
  #   Un truc bizarre se passe dans pytest_html, qui "refait" les rapports, donc on passe 2 fois ici
  #   for test_report in test_reports:
  #     print("           ----> ", test_report.when, test_report.outcome, test_report.longrepr)
  #     print("\n"+"o"*100)
  # print("x"*100)

  # > Tentative finalize :
  # for test_name, test_reports in html.reports.items():
  #   for test_report in test_reports:
  #     if( test_report.longrepr and isinstance(test_report.longrepr, ExceptionChainRepr)):
  #       print("xoxo"*10)
  #       test_report.longrepr.addsection( "titi", "oooooo")
  #       test_report.longrepr.addsection( "toto", "iiiiii")

  if html:
    del config._html
    config.pluginmanager.unregister(html)

@pytest.mark.tryfirst
def pytest_sessionfinish(session):
  html = getattr(session, "_html", None)
  for i, item in enumerate(session.items):
    print("\n ****** "*10, dir(item))
    item.add_report_section("call", "titi", "ooo")

# --------------------------------------------------------------------------
# @pytest.mark.tryfirst
# def pytest_runtest_logreport(report):
#   # print("MPI:: pytest_runtest_logreport", report.when)
#   # print("MPI:: pytest_runtest_logreport oooooo ", report.longrepr)

#   # Chaque rang doit faire un rapport !
#   # Attention si le rang 0 n'a pas d'erreur il faut également créer l'objet


#   # print("x"*100, type(report), dir(report))
#   # if report.longrepr and isinstance(report.longrepr, ExceptionChainRepr):
#   #   print("oooooo", report.when, type(report.longrepr), dir(report.longrepr))
#   #   print(report.longrepr)
#   #   report.longrepr.addsection( "titi", "oooooo")
#   #   report.longrepr.addsection( "toto", "iiiiii")
#   # print("x"*100)
#     # report.longrepr += report.longrepr
#     # report.longrepr += report.longrepr
#   # print("MPI:: pytest_runtest_logreport", type(report.longrepr))
#   # print("MPI:: pytest_runtest_logreport", dir(report.longrepr))

#   # > Pour hook
#   # content_out = report.capstdout
#   # content_log = report.caplog
#   # content_err = report.capstderr

#   pass

# --------------------------------------------------------------------------
@pytest.mark.tryfirst
def pytest_collectreport(report):
  print("MPI:: pytest_collectreport", report.when)
  # if report.failed:
  #   self.append_failed(report)

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

  comm   = MPI.COMM_WORLD

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

# A GARDER POUR LES SORTIES
# # if(comm.rank == i):
#   print("\n***************************", item.nodeid)
#   # print("***************************", item._sub_comm)
#   # print(i, item, dir(item), item.name, item.originalname)
#   # print("launch on {0} item : {1}".format(comm.rank, item))
#   # print(i, item)

#   # temp_ouput_file = 'maia_'
#   # sys.stdout = open(f"{temp_ouput_file(item.name)}_{MPI.COMM_WORLD.Get_rank()}", "w")
#   # sys.stdout = open(f"maia_{item.name}_{MPI.COMM_WORLD.Get_rank()}", "w")
#   # item.toto = i
#   # Create sub_comm !

# --------------------------------------------------------------------------
# @pytest.fixture
# def make_sub_comm(request):
#   """
#   """
#   comm = MPI.COMM_WORLD

#   # print(" request:: ", dir(request._pyfuncitem))
#   # print(" toto:: ", comm.rank, request._pyfuncitem.toto)
#   n_proc = request.param

#   # if(request._pyfuncitem.toto == comm.rank):
#   #   pytest.skip()
#   #   return None

#   return None

#   if(n_proc > comm.size):
#     pytest.skip()
#     return None

#   # Groups communicator creation
#   gprocs   = [i for i in range(n_proc)]
#   group    = comm.Get_group()
#   subgroup = group.Incl(gprocs)
#   # print(dir(comm))
#   # subcomm  = comm.Create(subgroup)      # Lock here - Collection among all procs
#   subcomm  = comm.Create_group(subgroup)  # Ok - Only collective amont groups

#   if(subcomm == MPI.COMM_NULL):
#     pytest.skip()

#   return subcomm

# def get_n_proc_for_test(item: Item) -> int :
#   # OOODLLLLDDDD
#   # exit(2)
#   # print("dir(item)::", dir(item.keywords))
#   # for mark in item.iter_markers(name="mpi_test"):
#   #   if mark.args:
#   #     raise ValueError("mpi mark does not take positional args")
#   #   n_proc_test = mark.kwargs.get('comm_size')

#   #   # print("**** item:: ", dir(item))
#   #   # print("**** request:: ", dir(item._pyfuncitem))
#   #   # print("**** request:: ", dir(item._pyfuncitem.funcargnames))
#   #   # print("**** request:: ", item._pyfuncitem.funcargnames)
#   #   # print("**** request:: ", item._pyfuncitem.funcargs)
#   #   # print("mark.kwargs::", mark.kwargs)
#   #   if(n_proc_test is None):
#   #     raise ValueError("We need to specify a comm_size for the test")
#   # return n_proc_test
