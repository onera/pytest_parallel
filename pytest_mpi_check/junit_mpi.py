
import py
import pytest

from mpi4py import MPI

from collections import defaultdict

from _pytest.nodes    import Item
from _pytest.junitxml import LogXML

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
    # print("HTMLReportMPI")
    LogXML.__init__(self, logfile, prefix, suite_name, logging, report_duration, family, log_passing_tests)

    self.comm         = comm
    self.mpi_reporter = mpi_reporter

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
    # ooooooooooooooooooooooooooooooooooooooooooooooooooooooo
    # > On gather tout
    # Il faut trier d'abord, pour un test la liste des rang.
    # Puis on refait depuis le debut le rapport
    for test_name, test_reports in self.mpi_reporter.mpi_reports.items():
      # print("test_name::", test_name)
      for test_report in test_reports:
        # print("test_report::", test_report.longrepr)

        # Seek the current report
        # print(type(self.node_reporters))
        # print(self.node_reporters)
        # try:
        lreport = self.node_reporters[(test_name[1], None)]
        # except KeyError:
        #   lreport = test_report

        # print(type(test_report))

        # greport.append(Junit(lreport.))
        # Il serai préférable de tout refaire :
        # TestReport() ...
        # see junitxml :: filename, lineno, skipreason = report.longrepr

        # > We find out the good report - Append
        if(test_report.longrepr):
          # print("type(test_report.longrepr) :: ", type(test_report.longrepr))
          # print("test_report.longrepr :: ", test_report.longrepr)
          # greport.longrepr.addsection(f" rank {test_name[0]}", test_report.longrepr)
          # greport.longrepr.addsection(f" rank {test_name[0]}", "oooo")
          lreport.append_failure(test_report)
          # print("*****"*100)
          # exit(1)
          # if greport.longrepr:
          #   greport.longrepr.addsection(f" rank {test_name[0]}", str(test_report.longrepr))
          # else:
          #   greport.longrepr = test_report.longrepr

          # if(test_report.outcome == 'failed'):
          #   # print(type(test_report.longrepr))
          #   # print(test_report.longrepr.chain[0][1])
          #   greport.outcome = test_report.outcome
    # ooooooooooooooooooooooooooooooooooooooooooooooooooooooo

    # self.reports = defaultdict(list)
    print("LogXMLMPI::pytest_sessionfinish")
    LogXML.pytest_sessionfinish(self)
