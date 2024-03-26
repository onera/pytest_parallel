# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import tempfile
import pytest
from pathlib import Path
from mpi4py import MPI


from .mpi_reporter import SequentialScheduler, StaticScheduler, DynamicScheduler
from .mpi_reporter import ProcessScheduler, ProcessWorker
from .utils import spawn_master_process, should_enable_terminal_reporter


# --------------------------------------------------------------------------
def pytest_addoption(parser):
    parser.addoption(
        '--scheduler',
        dest='scheduler',
        type='choice',
        choices=['sequential', 'static', 'dynamic', 'slurm'],
        default='sequential',
        help='Method used by pytest_parallel to schedule tests',
    )

    parser.addoption('--slurm-options', dest='slurm_options', type=str, help='list of SLURM options e.g. "--time=00:30:00 --qos=my_queue --n_tasks=4"')
    parser.addoption('--slurm-additional-cmds', dest='slurm_additional_cmds', type=str, help='list of commands to pass to SLURM job e.g. "source my_env.sh"')
    parser.addoption('--detach', dest='detach', action='store_true', help='Detach SLURM jobs: do not send reports to the scheduling process (useful to launch slurm job.sh separately)')

    # Private to SLURM scheduler
    parser.addoption('--_worker', dest='_worker', action='store_true', help='Internal pytest_parallel option')
    parser.addoption('--_scheduler_ip_address', dest='_scheduler_ip_address', type=str, help='Internal pytest_parallel option')
    parser.addoption('--_scheduler_port', dest='_scheduler_port', type=int, help='Internal pytest_parallel option')
    parser.addoption('--_test_idx'    , dest='_test_idx'    , type=int, help='Internal pytest_parallel option')

    # create SBATCH header
def parse_slurm_options(opt_str):
    opts = opt_str.split()
    for opt in opts:
      if '--ntasks' in opt:
          assert opt[0:len('--ntasks')] == '--ntasks', 'pytest_parallel SLURM scheduler: parsing error for `--ntasks`'
          ntasks_val = opt[len('--ntasks'):]
          assert ntasks_val[0]==' ' or ntasks_val[0]=='=', 'pytest_parallel SLURM scheduler: parsing error for `--ntasks`'
          try:
              ntasks = int(ntasks_val[1:])
          except ValueError:
              assert ntasks_val[0]==' ' or ntasks_val[0]=='=', 'pytest_parallel SLURM scheduler: parsing error for `--ntasks`'
          return ntasks, opts

    assert 0, 'pytest_parallel SLURM scheduler: you need specify `--ntasks` in `--slurm-options`'

# --------------------------------------------------------------------------
@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    global_comm = MPI.COMM_WORLD

    # Get options and check dependent/incompatible options
    scheduler = config.getoption('scheduler')
    slurm_options = config.getoption('slurm_options')
    slurm_additional_cmds = config.getoption('slurm_additional_cmds')
    slurm_worker = config.getoption('_worker')
    detach = config.getoption('detach')
    if scheduler != 'slurm':
        assert not slurm_worker
        assert not slurm_options
        assert not slurm_additional_cmds

    if scheduler == 'sequential':
        plugin = SequentialScheduler(global_comm)
    elif scheduler == 'static':
        plugin = StaticScheduler(global_comm)
    elif scheduler == 'dynamic':
        inter_comm = spawn_master_process(global_comm)
        plugin = DynamicScheduler(global_comm, inter_comm)
    elif scheduler == 'slurm':
        if slurm_worker:
            scheduler_ip_address = config.getoption('_scheduler_ip_address')
            scheduler_port = config.getoption('_scheduler_port')
            test_idx = config.getoption('_test_idx')
            plugin = ProcessWorker(scheduler_ip_address, scheduler_port, test_idx, detach)
        else: # scheduler
            assert global_comm.Get_size() == 1, 'pytest_parallel usage error: \
                                                 when scheduling with SLURM, \
                                                 do not launch the scheduling itself in parallel \
                                                 (do NOT use `mpirun -np n pytest...`)'

            # List of all invoke options except slurm options
            ## reconstruct complete invoke string
            quoted_invoke_params = []
            for arg in config.invocation_params.args:
                if ' ' in arg and not '--slurm-options' in arg:
                    quoted_invoke_params.append("'"+arg+"'")
                else:
                    quoted_invoke_params.append(arg)
            main_invoke_params = ' '.join(quoted_invoke_params)
            ## pull `--slurm-options` appart for special treatement
            main_invoke_params = ''.join( main_invoke_params.split(f'--slurm-options={slurm_options}') )
            slurm_ntasks, slurm_options = parse_slurm_options(slurm_options)
            plugin = ProcessScheduler(main_invoke_params, slurm_ntasks, slurm_options, slurm_additional_cmds, detach)
    else:
        assert 0

    config.pluginmanager.register(plugin, 'pytest_parallel')

    # only report to terminal if master process
    if not should_enable_terminal_reporter(global_comm, scheduler, slurm_worker):
        terminal_reporter = config.pluginmanager.getplugin('terminalreporter')
        config.pluginmanager.unregister(terminal_reporter)


# --------------------------------------------------------------------------
@pytest.fixture
def comm(request):
    '''
    Returns the MPI Communicator created by pytest_parallel
    '''
    return request.node.sub_comm


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
