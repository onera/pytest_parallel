import pytest

from mpi4py import MPI
from collections import defaultdict

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

  # def pytest_runtest_logreport(self, report):
  #   """
  #   """
  #   HTMLReport.pytest_runtest_logreport(self, report)

  def pytest_sessionfinish(self, session):
    """
    """
    assert(self.mpi_reporter.post_done == True)

    # ooooooooooooooooooooooooooooooooooooooooooooooooooooooo
    # > On gather tout
    # Il faut trier d'abord, pour un test la liste des rang.
    # Puis on refait depuis le debut le rapport
    for test_name, test_reports in self.mpi_reporter.mpi_reports.items():
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
          # print("test_report.longrepr :: ", test_report.longrepr)
          # greport.longrepr.addsection(f" rank {test_name[0]}", test_report.longrepr)
          # greport.longrepr.addsection(f" rank {test_name[0]}", "oooo")
          # if greport.longrepr and not isinstance(greport.longrepr, tuple): # A regarder
          # print("type(greport.longrepr) = ", type(greport.longrepr))
          # print("type(greport) = ", type(greport))
          # filename, lineno, skipreason = greport.longrepr
          # print("filename, lineno, skipreason::", filename, lineno, skipreason)
          if greport.longrepr:
            greport.longrepr.addsection(f" rank {test_name[0]}", str(test_report.longrepr))
          else:
            greport.longrepr = test_report.longrepr

          if(test_report.outcome == 'failed'):
            greport.outcome = test_report.outcome
    # ooooooooooooooooooooooooooooooooooooooooooooooooooooooo

    HTMLReport.pytest_sessionfinish(self, session)

