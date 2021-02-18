
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
    """
    Do not report cause you redo it after the gather
    """
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

    # print("\n", self.comm.Get_rank(), "LogXMLMPI::pytest_sessionfinish flag 4")

    for i_report, report in self.mpi_reporter.reports_gather.items():
      # print(i_report, " ---> ", report)
      LogXML.pytest_runtest_logreport(self, report[0])

    LogXML.pytest_sessionfinish(self)
