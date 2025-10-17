import pytest
import pytest_parallel


@pytest.fixture
def my_fixture(comm):
    return comm.rank


@pytest_parallel.mark.parallel(2)
def test_fixture(my_fixture):
    assert my_fixture == 0 # should fail on proc 1
