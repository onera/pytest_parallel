import pytest

from mpi4py import MPI
from collections import defaultdict

from pytest_html.plugin import HTMLReport

# --------------------------------------------------------------------------
class HTMLReportMPI(HTMLReport):
  def __init__(self, comm, htmlpath, config):
    """
    """
    # print("HTMLReportMPI")
    HTMLReport.__init__(self, htmlpath, config)

    self.comm         = comm
    self.mpi_requests = defaultdict(list)
    self.n_send       = 0
    self.mpi_reports  = defaultdict(list)

  def pytest_runtest_logreport(self, report):
    """
    """
    # print("HTMLReportMPI::pytest_runtest_logreport", report.when)

    if(self.comm.Get_rank() != 0):
      # print(dir(self.comm))
      # > Attention report peut être gros (stdout dedans etc ...)
      req = self.comm.isend(report, dest=0, tag=self.n_send)
      self.n_send += 1

      self.mpi_requests[report.nodeid].append(req)
      # print("ooooo", report.nodeid)

    HTMLReport.pytest_runtest_logreport(self, report)

  def pytest_sessionfinish(self, session):
    """
    """
    nb_recv_tot = self.comm.reduce(self.n_send, root=0)
    # print("nb_recv_tot::", nb_recv_tot)

    for test_name, reqs in self.mpi_requests.items():
      for req in reqs:
        # print(" *********************************** WAIT ")
        req.wait()

    # Si rang 0 il faut Probe tout
    # print(self.comm.Iprobe.__doc__)
    # print(dir(self.comm))

    # ooooooooooooooooooooooooooooooooooooooooooooooooooooooo
    if self.comm.Get_rank() == 0:
      for i_msg in range(nb_recv_tot):
        status = MPI.Status()
        # print(dir(status))
        is_ok_to_recv = self.comm.Iprobe(MPI.ANY_SOURCE, MPI.ANY_TAG, status=status)
        if is_ok_to_recv:
          # print("Status :: ", status.Get_source(), status.Get_tag())
          report = self.comm.recv(source=status.Get_source(), tag=status.Get_tag())
          # > On fait un dictionnaire en attendant de faire list + tri indirect
          if report:
            self.mpi_reports[(status.Get_source(),report.nodeid)].append(report)

        # print(i_msg, " --> ", report.longrepr)

    self.comm.Barrier()
    # ooooooooooooooooooooooooooooooooooooooooooooooooooooooo

    # ooooooooooooooooooooooooooooooooooooooooooooooooooooooo
    # > On gather tout
    # Il faut trier d'abord, pour un test la liste des rang.
    # Puis on refait depuis le debut le rapport
    for test_name, test_reports in self.mpi_reports.items():
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
          print("test_report.longrepr :: ", test_report.longrepr)
          # greport.longrepr.addsection(f" rank {test_name[0]}", test_report.longrepr)
          # greport.longrepr.addsection(f" rank {test_name[0]}", "oooo")
          if greport.longrepr and not isinstance(greport.longrepr, tuple): # A regarder
            greport.longrepr.addsection(f" rank {test_name[0]}", str(test_report.longrepr))
          else:
            greport.longrepr = test_report.longrepr

          if(test_report.outcome == 'failed'):
            # print(type(test_report.longrepr))
            # print(test_report.longrepr.chain[0][1])
            greport.outcome = test_report.outcome
    # ooooooooooooooooooooooooooooooooooooooooooooooooooooooo

    # ooooooooooooooooooooooooooooooooooooooooooooooooooooooo
    # for test_name, test_reports in self.reports.items():
    #   for test_report in test_reports:
    #     if( test_report.longrepr and isinstance(test_report.longrepr, ExceptionChainRepr)):
    #       print("xoxo"*10)
    #       test_report.longrepr.addsection( "titi", "oooooo\n")
    #       test_report.longrepr.addsection( "toto", "iiiiii\n")
    # ooooooooooooooooooooooooooooooooooooooooooooooooooooooo

    # self.reports = defaultdict(list)
    # print("HTMLReportMPI::pytest_sessionfinish")
    HTMLReport.pytest_sessionfinish(self, session)

