import pytest

from mpi4py import MPI

from .mpi_reporter import SequentialScheduler, StaticScheduler, DynamicScheduler

from .utils import spawn_master_process, is_master_process


# --------------------------------------------------------------------------
def pytest_addoption(parser):
    parser.addoption(
        "--scheduler",
        dest="scheduler",
        type="choice",
        choices=["sequential", "static", "dynamic"],
        default="sequential",
    )

## TODO move to fixtures.py
@pytest.fixture
def comm(request):
    """
    Only return a previous MPI Communicator (build at prepare step )
    """
    return request._pyfuncitem._sub_comm  # TODO clean


## TODO backward compatibility begin
@pytest.fixture
def sub_comm(request):
    return request._pyfuncitem._sub_comm


## TODO backward compatibility end


# --------------------------------------------------------------------------
@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    global_comm = MPI.COMM_WORLD

    scheduler = config.getoption("scheduler")
    if scheduler == "sequential":
        plugin = SequentialScheduler(global_comm)
    elif scheduler == "static":
        plugin = StaticScheduler(global_comm)
    elif scheduler == "dynamic":
        inter_comm = spawn_master_process(global_comm)
        plugin = DynamicScheduler(global_comm, inter_comm)
    else:
        assert 0

    config.pluginmanager.register(plugin, "pytest_parallel")

    # only report to terminal if master process
    if not is_master_process(global_comm, scheduler):
        terminal_reporter = config.pluginmanager.getplugin("terminalreporter")
        config.pluginmanager.unregister(terminal_reporter)
