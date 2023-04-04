import pytest
from _pytest.reports import TestReport
from _pytest._code.code import ExceptionChainRepr, ReprTraceback, ReprEntry, ReprEntryNative

from mpi4py import MPI
from collections import defaultdict

from _pytest.terminal   import TerminalReporter

# from _pytest.config import ExitCode
# from _pytest.main import Session

class TerminalReporterMPI(TerminalReporter):
  # __slots__ = ["comm", "mpi_reporter", "reports"]
  def __init__(self, comm, config, file, mpi_reporter):
    """
    """
    TerminalReporter.__init__(self, config, file)

    self.comm         = comm
    self.mpi_reporter = mpi_reporter

  #def pytest_runtest_logreport(self, report):
  #  """
  #  Do not report cause you redo it after the gather
  #  """
  #  pass


