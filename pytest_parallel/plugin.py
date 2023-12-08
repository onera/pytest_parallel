# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import tempfile
import pytest
from pathlib import Path
from mpi4py import MPI
import os


from .mpi_reporter import SequentialScheduler, StaticScheduler, DynamicScheduler
from .mpi_reporter import ProcessScheduler, ProcessWorker
from .utils import spawn_master_process, should_enable_terminal_reporter, PROCESS_SCHEDULERS


# --------------------------------------------------------------------------
def pytest_addoption(parser):
    parser.addoption(
        '--scheduler',
        dest='scheduler',
        type='choice',
        choices=['sequential', 'static', 'dynamic', 'shell', 'slurm'],
        default='sequential',
    )

    parser.addoption('--max_n_proc', dest='max_n_proc', type=int)

    # Private to SLURM scheduler
    parser.addoption('--_worker', dest='_worker', action='store_true')
    parser.addoption('--_scheduler_ip_address', dest='_scheduler_ip_address', type=str)
    parser.addoption('--_scheduler_port', dest='_scheduler_port', type=int)
    parser.addoption('--_test_idx'    , dest='_test_idx'    , type=int)

# --------------------------------------------------------------------------
@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    global_comm = MPI.COMM_WORLD

    scheduler = config.getoption('scheduler')
    if scheduler == 'sequential':
        plugin = SequentialScheduler(global_comm)
    elif scheduler == 'static':
        plugin = StaticScheduler(global_comm)
    elif scheduler == 'dynamic':
        inter_comm = spawn_master_process(global_comm)
        plugin = DynamicScheduler(global_comm, inter_comm)
    elif scheduler == 'slurm':
        if config.getoption('_worker'):
            n_working_procs = config.getoption('max_n_proc')
            scheduler_ip_address = config.getoption('_scheduler_ip_address')
            scheduler_port = config.getoption('_scheduler_port')
            test_idx = config.getoption('_test_idx')
            plugin = ProcessWorker(n_working_procs, scheduler_ip_address, scheduler_port, test_idx)
        else:
            assert global_comm.Get_size() == 1, 'pytest_parallel usage error: when scheduling with SLURM, do not launch the scheduling itself in parallel (do NOT use `mpirun ...`)'

            n_working_procs = int(config.getoption('max_n_proc'))
            plugin = ProcessScheduler(n_working_procs, scheduler)
    else:
        assert 0

    config.pluginmanager.register(plugin, 'pytest_parallel')

    # only report to terminal if master process
    if not should_enable_terminal_reporter(global_comm, scheduler):
        terminal_reporter = config.pluginmanager.getplugin('terminalreporter')
        config.pluginmanager.unregister(terminal_reporter)


# --------------------------------------------------------------------------
@pytest.fixture
def comm(request):
    '''
    Only return a previous MPI Communicator (build at prepare step )
    '''
    return request.node.sub_comm  # TODO clean


# --------------------------------------------------------------------------
class CollectiveTemporaryDirectory:
    '''
    Context manager creating a tmp dir in parallel and removing it at the
    exit
    '''

    def __init__(self, comm):
        self.comm = comm
        self.tmp_dir = None
        self.tmp_path = None

    def __enter__(self):
        rank = self.comm.Get_rank()
        self.tmp_dir = tempfile.TemporaryDirectory() if rank == 0 else None
        self.tmp_path = Path(self.tmp_dir.name) if rank == 0 else None
        return self.comm.bcast(self.tmp_path, root=0)

    def __exit__(self, type, value, traceback):
        self.comm.barrier()
        if self.comm.Get_rank() == 0:
            self.tmp_dir.cleanup()


@pytest.fixture
def mpi_tmpdir(comm):
    '''
    This function ensure that one process handles the naming of temporary folders.
    '''
    with CollectiveTemporaryDirectory(comm) as tmpdir:
        yield tmpdir
