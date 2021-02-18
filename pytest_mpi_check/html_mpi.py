import pytest
from _pytest.reports import TestReport
from _pytest._code.code import ExceptionChainRepr, ReprTraceback, ReprEntry, ReprEntryNative
# from _pytest._code.code import ReprTraceback
# from _pytest._code.code import ReprTraceback

from mpi4py import MPI
from collections import defaultdict
from copy import copy

from pytest_html.plugin import HTMLReport

class HTMLReportMPI(HTMLReport):
  __slots__ = ["comm", "mpi_reporter"]
  def __init__(self, comm, htmlpath, config, mpi_reporter):
    """
    """
    # print("HTMLReportMPI")
    HTMLReport.__init__(self, htmlpath, config)

    self.comm         = comm
    self.mpi_reporter = mpi_reporter

  def pytest_runtest_logreport(self, report):
    """
    Do not report cause you redo it after the gather
    """
    # HTMLReport.pytest_runtest_logreport(self, report)
    pass

  def pytest_sessionfinish(self, session):
    """
    """
    # print("pytest_sessionfinish:: ", len(self.mpi_reporter.mpi_reports.items()))

    assert(self.mpi_reporter.post_done == True)
    # print("\n", self.comm.Get_rank(), "HTMLReportMPI::pytest_sessionfinish flag 4")

    for i_report, report in self.mpi_reporter.reports_gather.items():
      # print(i_report, " ---> ", report)
      #Copy is mandatory because pytest-html v3.1.1 refill test_report.longrepr with a string instead
      #of tuple (see pytest_html/plugin.py, l730)
      HTMLReport.pytest_runtest_logreport(self, copy(report[0]))
    HTMLReport.pytest_sessionfinish(self, session)


























# ------------------------------------------------------------------------
  # def pytest_sessionfinish(self, session):
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

  #     collect_longrepr = []
  #     # i_rank_report_init
  #     # if(report_init.longrepr):
  #     #   greport.longrepr = report_init.longrepr
  #     #   fake_trace_back_init = ReprTraceback([ReprEntryNative(f"\n\n ----------------------- On rank {i_rank_report_init} ----------------------- \n\n")], None, None)
  #     #   # greport.longrepr = ExceptionChainRepr([(fake_trace_back_init, None, None)])

  #     #   collect_longrepr.append( (fake_trace_back_init, None, None) )
  #       # collect_longrepr.append( (report_init.longrepr, None, None))

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
  #         collect_longrepr.append((test_report.longrepr, None, None))

  #     # print("******")
  #     # for i_collect in collect_longrepr:
  #     #   print(" -----> ", type(i_collect), i_collect)
  #     # print("******")

  #     if(len(collect_longrepr) > 0):
  #       greport.longrepr = ExceptionChainRepr(collect_longrepr)

  #     self.reports[nodeid] = [greport]
  #   # -----------------------------------------------------------------

  #   print("len(self.reports)::", len(self.reports))
  #   HTMLReport.pytest_sessionfinish(self, session)


  #   return

  #   # ooooooooooooooooooooooooooooooooooooooooooooooooooooooo
  #   # > On gather tout
  #   # Il faut trier d'abord, pour un test la liste des rang.
  #   # Puis on refait depuis le debut le rapport
  #   for test_name, test_reports in self.mpi_reporter.mpi_reports.items():
  #     # print("test_name::", test_name)
  #     for test_report in test_reports:
  #       print("test_report::", test_report)

  #       if(test_report is None):
  #         continue

  #       # Seek the current report
  #       lreports = self.reports[test_name[1]]
  #       greport = None
  #       for lreport in lreports:
  #         print("test_report.when     == ", test_report.when )
  #         print("lreport    .when     == ", lreport.when     )
  #         print("lreport    .location == ", lreport.location )
  #         if(test_report.when == lreport.when ):
  #           greport = lreport

  #       # Il serai préférable de tout refaire :
  #       # TestReport() ...
  #       # see junitxml :: filename, lineno, skipreason = report.longrepr

  #       # > We find out the good report - Append
  #       if(test_report.longrepr):
  #         # print("type(test_report.longrepr) :: ", type(test_report.longrepr))
  #         # print("test_report.longrepr :: ", test_report.longrepr)
  #         # greport.longrepr.addsection(f" rank {test_name[0]}", test_report.longrepr)
  #         # greport.longrepr.addsection(f" rank {test_name[0]}", "oooo")
  #         # if greport.longrepr and not isinstance(greport.longrepr, tuple): # A regarder
  #         # print("type(greport.longrepr) = ", type(greport.longrepr))
  #         # print("type(greport) = ", type(greport))
  #         # filename, lineno, skipreason = greport.longrepr
  #         # print("filename, lineno, skipreason::", filename, lineno, skipreason)
  #         if not greport:
  #           continue
  #         elif greport.longrepr:
  #           greport.longrepr.addsection(f" rank {test_name[0]}", str(test_report.longrepr))
  #         else:
  #           greport.longrepr = test_report.longrepr

  #         if(test_report.outcome == 'failed'):
  #           greport.outcome = test_report.outcome
  #   # ooooooooooooooooooooooooooooooooooooooooooooooooooooooo

  #   HTMLReport.pytest_sessionfinish(self, session)


        # tmp = report_init.longrepr.chain[0]
        # tmp[2] = "titit"
        # report_init.longrepr.chain.append( report_init.longrepr.chain[0])
        # report_init.longrepr.chain.append( (tmp[0], tmp[1], "-"*100))
        # greport.longrepr.addsection(f" rank {i_rank_report_init}", str(report_init.longrepr))
        # greport.longrepr.addsection(f" rank {i_rank_report_init}", str(report_init.longrepr))

        # print("report_init.longrepr.chain::", type(report_init.longrepr), report_init.longrepr.chain)
        # print("*"*100)
        # print("report_init.longrepr.chain[0][0]::", type(report_init.longrepr.chain[0][0]), report_init.longrepr.chain[0][0].reprentries)
        # print("*"*100)
        # print("*"*100)
        # print("report_init.longrepr.chain[0][0]::", type(report_init.longrepr.chain[0][0]), report_init.longrepr.chain[0][0].extraline)
        # print("*"*100)
        # print("*"*100)
        # print("report_init.longrepr.chain[0][0]::", type(report_init.longrepr.chain[0][0]), report_init.longrepr.chain[0][0].style)
        # print("*"*100)
