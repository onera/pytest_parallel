import pytest

from mpi4py import MPI
from collections import defaultdict

class MPIReporter(object):
  __slots__ = ["mpi_reports", "comm", "n_send", "post_done"]
  def __init__(self, comm):
    self.comm         = comm
    self.n_send       = 0
    self.mpi_reports  = defaultdict(list)
    self.post_done    = False

  @pytest.mark.tryfirst
  def pytest_runtest_logreport(self, report):
    """
    """
    # print("MPIReporter::pytest_runtest_logreport", report.when)

    # if(self.comm.Get_rank() != 0):
    if(self.comm.Get_rank() >= 0 and (report.skipped == False)):
      # > Attention report peut être gros (stdout dedans etc ...)
      self.comm.send(report, dest=0, tag=self.n_send)
      self.n_send += 1

  @pytest.mark.tryfirst
  def pytest_sessionfinish(self, session):
    """
    """
    nb_recv_tot = self.comm.reduce(self.n_send, root=0)

    self.comm.Barrier()

    if self.comm.Get_rank() == 0:
      for i_msg in range(nb_recv_tot):
        status = MPI.Status()
        # print(dir(status))
        is_ok_to_recv = self.comm.probe(MPI.ANY_SOURCE, MPI.ANY_TAG, status=status)
        if is_ok_to_recv:
          report = self.comm.recv(source=status.Get_source(), tag=status.Get_tag())
          # > On fait un dictionnaire en attendant de faire list + tri indirect
          if report:
            self.mpi_reports[(status.Get_source(),report.nodeid)].append(report)

    self.comm.Barrier()

    self.post_done = True
