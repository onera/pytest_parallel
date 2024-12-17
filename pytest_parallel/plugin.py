# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import os
import sys
import subprocess
import tempfile
from pathlib import Path
import argparse
import resource
import pytest
from _pytest.terminal import TerminalReporter
#import signal

# --------------------------------------------------------------------------
def pytest_addoption(parser):
    #def sig_handler(sig, frame):
    #  print(f'\n\n\n\nSIGNAL_HANDLER caught {sig}')
    #signal.signal(11, sig_handler)

    parser.addoption(
        '--scheduler',
        dest='scheduler',
        choices=['sequential', 'static', 'dynamic', 'slurm', 'shell'],
        default='sequential',
        help='Method used by pytest_parallel to schedule tests',
    )

    parser.addoption('--n-workers', dest='n_workers', type=int, help='Max number of processes to run in parallel')

    parser.addoption('--timeout', dest='timeout', type=int, default=7200, help='Timeout')

    parser.addoption('--slurm-options', dest='slurm_options', type=str, help='list of SLURM options e.g. "--time=00:30:00 --qos=my_queue --n_tasks=4"')
    parser.addoption('--slurm-srun-options', dest='slurm_srun_options', type=str, help='list of SLURM srun options e.g. "--mem-per-cpu=4GB"')
    parser.addoption('--slurm-additional-cmds', dest='slurm_additional_cmds', type=str, help='list of commands to pass to SLURM job e.g. "source my_env.sh"')
    parser.addoption('--slurm-file', dest='slurm_file', type=str, help='Path to file containing header of SLURM job') # TODO DEL
    parser.addoption('--slurm-sub-command', dest='slurm_sub_command', type=str, help='SLURM submission command (defaults to `sbatch`)') # TODO DEL

    if sys.version_info >= (3,9):
        parser.addoption('--slurm-export-env', dest='slurm_export_env', action=argparse.BooleanOptionalAction, default=True)
    else:
        parser.addoption('--slurm-export-env', dest='slurm_export_env', default=False, action='store_true')
        parser.addoption('--no-slurm-export-env', dest='slurm_export_env', action='store_false')

    parser.addoption('--detach', dest='detach', action='store_true', help='Detach SLURM jobs: do not send reports to the scheduling process (useful to launch slurm job.sh separately)')

    # Private to shell schedulers (slurm and shell)
    parser.addoption('--_worker', dest='_worker', action='store_true', help='Internal pytest_parallel option')
    parser.addoption('--_scheduler_ip_address', dest='_scheduler_ip_address', type=str, help='Internal pytest_parallel option')
    parser.addoption('--_scheduler_port', dest='_scheduler_port', type=int, help='Internal pytest_parallel option')
    parser.addoption('--_test_idx'    , dest='_test_idx'    , type=int, help='Internal pytest_parallel option')

    # Note:
    #    we need to NOT import mpi4py when pytest_parallel
    #    is called with the SLURM scheduler
    #    because it can mess SLURM `srun`
    if "--scheduler=slurm" in sys.argv:
        assert 'mpi4py.MPI' not in sys.modules, 'Internal pytest_parallel error: mpi4py.MPI should not be imported' \
                                               ' when we are about to register and environment for SLURM' \
                                               ' (because importing mpi4py.MPI makes the current process look like and MPI process,' \
                                               ' and SLURM does not like that)'

        r = subprocess.run(['env','--null'], stdout=subprocess.PIPE) # `--null`: end each output line with NUL, required by `sbatch --export-file`

        assert r.returncode==0, 'SLURM scheduler: error when writing `env` to `pytest_slurm/env_vars.sh`'
        pytest._pytest_parallel_env_vars = r.stdout

# --------------------------------------------------------------------------
def _invoke_params(args):
    quoted_invoke_params = []
    for arg in args:
        if ' ' in arg and not '--slurm-options' in arg:
            quoted_invoke_params.append("'"+arg+"'")
        else:
            quoted_invoke_params.append(arg)
    return ' '.join(quoted_invoke_params)

# --------------------------------------------------------------------------
@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    # Set timeout
    timeout = config.getoption('timeout')
    resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout))

    # Get options and check dependent/incompatible options
    scheduler = config.getoption('scheduler')
    n_workers = config.getoption('n_workers')
    slurm_options = config.getoption('slurm_options')
    slurm_srun_options = config.getoption('slurm_srun_options')
    slurm_additional_cmds = config.getoption('slurm_additional_cmds')
    is_worker = config.getoption('_worker')
    slurm_file = config.getoption('slurm_file')
    slurm_export_env = config.getoption('slurm_export_env')
    slurm_sub_command = config.getoption('slurm_sub_command')
    detach = config.getoption('detach')
    if scheduler != 'slurm' and scheduler != 'shell':
        assert not is_worker, 'Option `--slurm-worker` only available when `--scheduler=slurm` or `--scheduler=shell`'
    if (scheduler == 'slurm' or scheduler == 'shell') and not is_worker:
        assert n_workers, f'You need to specify `--n-workers` when `--scheduler={scheduler}`'
    if scheduler != 'slurm':
        assert not slurm_options, 'Option `--slurm-options` only available when `--scheduler=slurm`'
        assert not slurm_srun_options, 'Option `--slurms-run-options` only available when `--scheduler=slurm`'
        assert not slurm_additional_cmds, 'Option `--slurm-additional-cmds` only available when `--scheduler=slurm`'
        assert not slurm_file, 'Option `--slurm-file` only available when `--scheduler=slurm`'

    if (scheduler == 'shell' or scheduler == 'slurm') and not is_worker:
        from mpi4py import MPI
        assert MPI.COMM_WORLD.size == 1, 'Do not launch `pytest_parallel` on more that one process\n' \
                                         'when `--scheduler=shell` or `--scheduler=slurm`.\n' \
                                         '`pytest_parallel` spawn mpi processes itself.\n' \
                                         f'You may want to use --n-workers={MPI.COMM_WORLD.size}.'



    if scheduler == 'slurm' and not is_worker:
        assert slurm_options or slurm_file, 'You need to specify either `--slurm-options` or `--slurm-file` when `--scheduler=slurm`'
        if slurm_options:
            assert not slurm_file, 'You need to specify either `--slurm-options` or `--slurm-file`, but not both'
        if slurm_file:
            assert not slurm_options, 'You need to specify either `--slurm-options` or `--slurm-file`, but not both'
            assert not slurm_additional_cmds, 'You cannot specify `--slurm-additional-cmds` together with `--slurm-file`'

        from .process_scheduler import ProcessScheduler

        enable_terminal_reporter = True

        # List of all invoke options except slurm options
        ## reconstruct complete invoke string
        main_invoke_params = _invoke_params(config.invocation_params.args)
        ## pull apart `--slurm-options` for special treatement
        main_invoke_params = main_invoke_params.replace(f'--slurm-options={slurm_options}', '')
        for file_or_dir in config.option.file_or_dir:
          main_invoke_params = main_invoke_params.replace(file_or_dir, '')
        slurm_option_list = slurm_options.split() if slurm_options is not None else []
        slurm_conf = {
            'options'        : slurm_option_list,
            'srun_options'   : slurm_srun_options,
            'additional_cmds': slurm_additional_cmds,
            'file'           : slurm_file,
            'export_env'     : slurm_export_env,
            'sub_command'    : slurm_sub_command,
        }
        plugin = ProcessScheduler(main_invoke_params, n_workers, slurm_conf, detach)

    elif scheduler == 'shell' and not is_worker:
        from .shell_static_scheduler import ShellStaticScheduler
        enable_terminal_reporter = True

        # reconstruct complete invoke string
        main_invoke_params = _invoke_params(config.invocation_params.args)
        for file_or_dir in config.option.file_or_dir:
          main_invoke_params = main_invoke_params.replace(file_or_dir, '')
        plugin = ShellStaticScheduler(main_invoke_params, n_workers, detach)
    else:
        from mpi4py import MPI
        from .mpi_reporter import SequentialScheduler, StaticScheduler, DynamicScheduler
        from .process_worker import ProcessWorker
        from .utils_mpi import spawn_master_process, should_enable_terminal_reporter

        global_comm = MPI.COMM_WORLD
        enable_terminal_reporter = should_enable_terminal_reporter(global_comm, scheduler)

        if scheduler == 'sequential':
            plugin = SequentialScheduler(global_comm)
        elif scheduler == 'static':
            plugin = StaticScheduler(global_comm)
        elif scheduler == 'dynamic':
            inter_comm = spawn_master_process(global_comm)
            plugin = DynamicScheduler(global_comm, inter_comm)
        elif (scheduler == 'slurm' or scheduler == 'shell') and is_worker:
            scheduler_ip_address = config.getoption('_scheduler_ip_address')
            scheduler_port = config.getoption('_scheduler_port')
            test_idx = config.getoption('_test_idx')
            plugin = ProcessWorker(scheduler_ip_address, scheduler_port, test_idx, detach)
        else:
            assert 0

    config.pluginmanager.register(plugin, 'pytest_parallel')

    # only report to terminal if master process
    if not enable_terminal_reporter:
        # unregister the stdout terminal reporter
        terminal_reporter = config.pluginmanager.getplugin('terminalreporter')
        config.pluginmanager.unregister(terminal_reporter)

        # Pytest relies on having a terminal reporter to decide on how to create error messages, see #12
        # Hence, register a terminal reporter that outputs to /dev/null
        null_file = open(os.devnull,'w')
        terminal_reporter = TerminalReporter(config, null_file)
        config.pluginmanager.register(terminal_reporter, "terminalreporter")


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
        from mpi4py import MPI
        if self.comm != MPI.COMM_NULL: # TODO DEL once non-participating rank do not participate in fixtures either
            rank = self.comm.Get_rank()
            self.tmp_dir = tempfile.TemporaryDirectory() if rank == 0 else None
            self.tmp_path = Path(self.tmp_dir.name) if rank == 0 else None
            return self.comm.bcast(self.tmp_path, root=0)

    def __exit__(self, type, value, traceback):
        from mpi4py import MPI
        if self.comm != MPI.COMM_NULL: # TODO DEL once non-participating rank do not participate in fixtures either
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
