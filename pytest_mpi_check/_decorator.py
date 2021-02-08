import pytest

@pytest.fixture
def sub_comm(request):
  """
  Only return a previous MPI Communicator (build at prepare step )
  """
  return request._pyfuncitem._sub_comm
