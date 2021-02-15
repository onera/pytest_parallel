
import py
import pytest

from mpi4py import MPI

from collections import defaultdict

from _pytest.nodes    import Item
from _pytest.junitxml import LogXML
from _pytest.reports import TestReport
from _pytest._code.code import ExceptionChainRepr, ReprTraceback, ReprEntry, ReprEntryNative

class Junit(py.xml.Namespace):
    pass

# --------------------------------------------------------------------------
class LogXMLMPI(LogXML):
  __slots__ = ["comm", "mpi_reporter"]
  def __init__(self,
               comm,
               mpi_reporter,
               logfile,
               prefix,
               suite_name="pytest",
               logging="no",
               report_duration="total",
               family="xunit1",
               log_passing_tests=True):
    """
    """
    LogXML.__init__(self, logfile, prefix, suite_name, logging, report_duration, family, log_passing_tests)

    self.comm         = comm
    self.mpi_reporter = mpi_reporter

  def pytest_runtest_logreport(self, report):
    # LogXML.pytest_runtest_logreport(self, report)
    pass

  def finalize(self, report):
    """
    Little hack to not dstroy internal map (Mandaoty to keep this map)
    """
    # print("LogXMLMPI::finalize")
    pass

  def pytest_sessionfinish(self, session):
    """
    """
    assert(self.mpi_reporter.post_done == True)

    print(self.comm.Get_rank(), " pytest_sessionfinish flag 4")

    for i_report, report in self.mpi_reporter.reports_gather.items():
      # print(i_report, " ---> ", report)
      LogXML.pytest_runtest_logreport(self, report[0])


    LogXML.pytest_sessionfinish(self)


  # def pytest_sessionfinish_old(self, session):
  #   """
  #   """
  #   assert(self.mpi_reporter.post_done == True)

  #   print(self.comm.Get_rank(), " pytest_sessionfinish flag 4")

  #   for i, j in self.node_reporters.items():
  #     print(self.comm.Get_rank(), " --> ", i,j)

  #   # -----------------------------------------------------------------
  #   for nodeid, report_list in self.mpi_reporter.mpi_reports.items():
  #     # print("nodeid::", nodeid)

  #     assert(len(report_list) > 0)

  #     # > Initialize with the first reporter
  #     i_rank_report_init, report_init = report_list[0]

  #     greport = TestReport(nodeid,
  #                          report_init.location,
  #                          report_init.keywords,
  #                          report_init.outcome,
  #                          None, # longrepr
  #                          report_init.when)

  #     # print("report_init.location::", report_init.location)
  #     # print("report_init.longrepr::", type(report_init.longrepr), report_init.longrepr)


  #     # 2 solutions = Soit on revoit l'execution de la boucle runtent_protocol
  #     # Soit on refait l'enrigtrement à la fin de tout les tests ---> C'est à dire qu'on rapelle  def pytest_runtest_logreport(self, report):
  #     # Une fois le rapport "gather"
  #     # Attention dans l'implem junit il y a à la fois le dictionnaire ET la list

  #     try:
  #       lreport = self.node_reporters[(nodeid, None)]
  #     except KeyError:
  #       continue

  #     collect_longrepr = []
  #     # # i_rank_report_init
  #     # if(report_init.longrepr):
  #     #   greport.longrepr = report_init.longrepr
  #     #   fake_trace_back_init = ReprTraceback([ReprEntryNative(f"\n\n ----------------------- On rank {i_rank_report_init} ----------------------- \n\n")], None, None)
  #     #   # greport.longrepr = ExceptionChainRepr([(fake_trace_back_init, None, None)])

  #     #   collect_longrepr.append( (fake_trace_back_init, None, None) )
  #     #   # collect_longrepr.append( (report_init.longrepr, None, None))

  #     # > We need to rebuild a TestReport object, location can be false
  #     # > Report appears in rank increasing order
  #     for i_rank_report, test_report  in report_list:
  #     # for i_rank_report, test_report  in report_list:
  #       # print("test_report::", i_rank_report, test_report)

  #       if(test_report.outcome == 'failed'):
  #         greport.outcome = test_report.outcome

  #       if(test_report.longrepr):

  #         fake_trace_back = ReprTraceback([ReprEntryNative(f"\n\n----------------------- On rank {i_rank_report} ----------------------- \n\n")], None, None)

  #         collect_longrepr.append((fake_trace_back     , None, None))

  #         lreport.append_failure(test_report)

  #     if(len(collect_longrepr) > 0):
  #       greport.longrepr = ExceptionChainRepr(collect_longrepr)

  #     # self.reports[nodeid] = [greport]
  #     print("nodeid::", nodeid)
  #     # self.node_reporters[(nodeid, None)] = greport
  #   # -----------------------------------------------------------------

  #   print("***********")
  #   for i, j in self.node_reporters.items():
  #     print(i,j)
  #   print("***********")

  #   print("LogXMLMPI::pytest_sessionfinish")
  #   LogXML.pytest_sessionfinish(self)
  #   return

  #   # ooooooooooooooooooooooooooooooooooooooooooooooooooooooo
  #   # > On gather tout
  #   # Il faut trier d'abord, pour un test la liste des rang.
  #   # Puis on refait depuis le debut le rapport
  #   for test_name, test_reports in self.mpi_reporter.mpi_reports.items():
  #     # print("test_name::", test_name)
  #     for test_report in test_reports:
  #       # print("test_report::", test_report.longrepr)

  #       # Seek the current report
  #       # print(type(self.node_reporters))
  #       # print(self.node_reporters)
  #       # try:
  #       lreport = self.node_reporters[(test_name[1], None)]
  #       # except KeyError:
  #       #   lreport = test_report

  #       # print(type(test_report))

  #       # greport.append(Junit(lreport.))
  #       # Il serai préférable de tout refaire :
  #       # TestReport() ...
  #       # see junitxml :: filename, lineno, skipreason = report.longrepr

  #       # > We find out the good report - Append
  #       if(test_report.longrepr):
  #         # print("type(test_report.longrepr) :: ", type(test_report.longrepr))
  #         # print("test_report.longrepr :: ", test_report.longrepr)
  #         # greport.longrepr.addsection(f" rank {test_name[0]}", test_report.longrepr)
  #         # greport.longrepr.addsection(f" rank {test_name[0]}", "oooo")
  #         lreport.append_failure(test_report)
  #         # print("*****"*100)
  #         # exit(1)
  #         # if greport.longrepr:
  #         #   greport.longrepr.addsection(f" rank {test_name[0]}", str(test_report.longrepr))
  #         # else:
  #         #   greport.longrepr = test_report.longrepr

  #         # if(test_report.outcome == 'failed'):
  #         #   # print(type(test_report.longrepr))
  #         #   # print(test_report.longrepr.chain[0][1])
  #         #   greport.outcome = test_report.outcome
  #   # ooooooooooooooooooooooooooooooooooooooooooooooooooooooo

  #   # self.reports = defaultdict(list)
  #   print("LogXMLMPI::pytest_sessionfinish")
  #   LogXML.pytest_sessionfinish(self)
