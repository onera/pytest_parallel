# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import os
import sys
import subprocess
import tempfile
from pathlib import Path
import argparse

import pytest
from _pytest.terminal import TerminalReporter

class PytestParallelError(ValueError):
    pass

# --------------------------------------------------------------------------
def pytest_addoption(parser):
    parser.addoption(
        '--scheduler',
        dest='scheduler',
        choices=['sequential', 'static', 'dynamic', 'slurm', 'shell'],
        default='dynamic',
        help='Method used by pytest_parallel to schedule tests',
    )

    parser.addoption('--n-workers', dest='n_workers', type=int, help='Max number of processes to run in parallel')

    parser.addoption('--timeout', dest='timeout', type=int, default=7200, help='Timeout')

    parser.addoption('--slurm-options', dest='slurm_options', type=str, help='list of SLURM options e.g. "--time=00:30:00 --qos=my_queue"')
    parser.addoption('--slurm-srun-options', dest='slurm_srun_options', type=str, help='list of SLURM srun options e.g. "--mem-per-cpu=4GB"')
    parser.addoption('--slurm-init-cmds', dest='slurm_init_cmds', type=str, help='list of commands to pass to SLURM job e.g. "source my_env.sh"')
    parser.addoption('--slurm-file', dest='slurm_file', type=str, help='Path to file containing header of SLURM job') # TODO DEL

    if sys.version_info >= (3,9):
        parser.addoption('--slurm-export-env', dest='slurm_export_env', action=argparse.BooleanOptionalAction, default=True)
        parser.addoption('--use-srun', dest='use_srun', action=argparse.BooleanOptionalAction, default=None, help='Launch MPI processes through srun (only possible when `--scheduler=shell`')
    else:
        parser.addoption('--slurm-export-env', dest='slurm_export_env', default=False, action='store_true')
        parser.addoption('--no-slurm-export-env', dest='slurm_export_env', action='store_false')
        parser.addoption('--use-srun', dest='use_srun', default=None, action='store_true')

    parser.addoption('--detach', dest='detach', action='store_true', help='Detach SLURM jobs: do not send reports to the scheduling process (useful to launch slurm job.sh separately)')

    # Private to shell schedulers (slurm and shell)
    parser.addoption('--_worker', dest='_worker', action='store_true', help='Internal pytest_parallel option')
    parser.addoption('--_scheduler_ip_address', dest='_scheduler_ip_address', type=str, help='Internal pytest_parallel option')
    parser.addoption('--_scheduler_port', dest='_scheduler_port', type=int, help='Internal pytest_parallel option')
    parser.addoption('--_session_folder', dest='_session_folder', type=str, help='Internal pytest_parallel option')
    parser.addoption('--_test_idx'    , dest='_test_idx'    , type=int, help='Internal pytest_parallel option')

    # Note:
    #    we need to NOT import mpi4py when pytest_parallel
    #    is called with the SLURM scheduler
    #    because it can mess SLURM `srun`
    if "--scheduler=slurm" in sys.argv:
        assert 'mpi4py.MPI' not in sys.modules, 'Internal pytest_parallel error: mpi4py.MPI should not be imported' \
                                                ' when we are about to register an environment for SLURM' \
                                                ' (because importing mpi4py.MPI makes the current process look like and MPI process,' \
                                                ' and SLURM does not like that)'
        if os.getenv('I_MPI_MPIRUN') is not None:
            err_msg =  'Internal pytest_parallel error: the environment variable I_MPI_MPIRUN is set' \
                      f' (it has value "{os.getenv("I_MPI_MPIRUN")}"),\n' \
                       ' while pytest was invoked with "--scheduler=slurm".\n' \
                       ' This indicates that pytest was run through MPI, and SLURM generally does not like that.\n' \
                       ' With "--scheduler=slurm", just run `pytest` directly, not through `mpirun/mpiexec/srun`,\n' \
                       ' because it will launch MPI itself (you may want to use --n-workers=<number of processes>).'
            raise PytestParallelError(err_msg)

        r = subprocess.run(['env','--null'], stdout=subprocess.PIPE) # `--null`: end each output line with NUL, required by `sbatch --export-file`

        assert r.returncode==0, 'Internal pytest_parallel SLURM schedule error: error when writing `env` to `pytest_slurm/env_vars.sh`'
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
def _set_timeout(timeout):
    if sys.platform != "win32":
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout))
    # if windows, we don't know how to do that

# --------------------------------------------------------------------------
@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    # Set timeout
    timeout = config.getoption('timeout')
    _set_timeout(timeout)

    # Get options and check dependent/incompatible options
    scheduler = config.getoption('scheduler')
    n_workers = config.getoption('n_workers')
    slurm_options = config.getoption('slurm_options')
    slurm_srun_options = config.getoption('slurm_srun_options')
    slurm_init_cmds = config.getoption('slurm_init_cmds')
    is_worker = config.getoption('_worker')
    slurm_file = config.getoption('slurm_file')
    slurm_export_env = config.getoption('slurm_export_env')
    use_srun = config.getoption('use_srun')
    detach = config.getoption('detach')
    if scheduler != 'shell':
        if use_srun is not None:
            raise PytestParallelError('Option `--use-srun` only available when `--scheduler=shell`')
    if not scheduler in ['slurm', 'shell']:
        assert not is_worker, f'Internal pytest_parallel error `--_worker` not available with`--scheduler={scheduler}`'
        assert not n_workers, f'pytest_parallel error `--n-workers` not available with`--scheduler={scheduler}`. Launch with `mpirun -np {n_workers}` to run in parallel'
    if scheduler in ['slurm', 'shell'] and not is_worker:
        if n_workers is None:
            raise PytestParallelError(f'You need to specify `--n-workers` when `--scheduler={scheduler}`')
    if scheduler != 'slurm':
        if slurm_options is not None:
            raise PytestParallelError('Option `--slurm-options` only available when `--scheduler=slurm`')
        if slurm_srun_options is not None:
            raise PytestParallelError('Option `--slurms-run-options` only available when `--scheduler=slurm`')
        if slurm_init_cmds is not None:
            raise PytestParallelError('Option `--slurm-init-cmds` only available when `--scheduler=slurm`')
        if slurm_file is not None:
            raise PytestParallelError('Option `--slurm-file` only available when `--scheduler=slurm`')

    if scheduler in ['shell', 'slurm'] and not is_worker:
        from mpi4py import MPI
        if MPI.COMM_WORLD.size != 1:
            err_msg = 'Do not launch `pytest_parallel` on more that one process when `--scheduler=shell` or `--scheduler=slurm`.\n' \
                      '`pytest_parallel` will spawn MPI processes itself.\n' \
                     f'You may want to use --n-workers={MPI.COMM_WORLD.size}.'
            raise PytestParallelError(err_msg)



    if scheduler == 'slurm' and not is_worker:
        if slurm_options is None and slurm_file is None:
            raise PytestParallelError('You need to specify either `--slurm-options` or `--slurm-file` when `--scheduler=slurm`')
        if slurm_options:
            if slurm_file:
                raise PytestParallelError('You need to specify either `--slurm-options` or `--slurm-file`, but not both')
        if slurm_file:
            if slurm_options:
                raise PytestParallelError('You need to specify either `--slurm-options` or `--slurm-file`, but not both')
            if slurm_init_cmds:
                raise PytestParallelError('You cannot specify `--slurm-init-cmds` together with `--slurm-file`')

        if '-n=' in slurm_options or '--ntasks=' in slurm_options:
            raise PytestParallelError('Do not specify `-n/--ntasks` in `--slurm-options` (it is deduced from the `--n-worker` value).')

        from .slurm_scheduler import SlurmScheduler

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
            'options'     : slurm_option_list,
            'srun_options': slurm_srun_options,
            'init_cmds'   : slurm_init_cmds,
            'file'        : slurm_file,
            'export_env'  : slurm_export_env,
        }
        plugin = SlurmScheduler(main_invoke_params, n_workers, slurm_conf, detach)

    elif scheduler == 'shell' and not is_worker:
        from .shell_static_scheduler import ShellStaticScheduler
        enable_terminal_reporter = True

        # reconstruct complete invoke string
        main_invoke_params = _invoke_params(config.invocation_params.args)
        for file_or_dir in config.option.file_or_dir:
            main_invoke_params = main_invoke_params.replace(file_or_dir, '')
        plugin = ShellStaticScheduler(main_invoke_params, n_workers, detach, use_srun)
    else:
        from mpi4py import MPI
        from .mpi_reporter import SequentialScheduler, StaticScheduler, DynamicScheduler
        from .process_worker import ProcessWorker
        from .utils.mpi import spawn_master_process, should_enable_terminal_reporter

        global_comm = MPI.COMM_WORLD
        enable_terminal_reporter = should_enable_terminal_reporter(global_comm, scheduler)

        if scheduler == 'sequential':
            plugin = SequentialScheduler(global_comm)
        elif scheduler == 'static':
            plugin = StaticScheduler(global_comm)
        elif scheduler == 'dynamic':
            inter_comm = spawn_master_process(global_comm)
            plugin = DynamicScheduler(global_comm, inter_comm)
        elif scheduler in ['shell', 'slurm'] and is_worker:
            scheduler_ip_address = config.getoption('_scheduler_ip_address')
            scheduler_port = config.getoption('_scheduler_port')
            session_folder = config.getoption('_session_folder')
            test_idx = config.getoption('_test_idx')
            plugin = ProcessWorker(scheduler_ip_address, scheduler_port, session_folder, test_idx, detach)
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
        null_file = open(os.devnull,'w', encoding='utf-8')
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
            rank = self.comm.rank
            self.tmp_dir = tempfile.TemporaryDirectory() if rank == 0 else None
            self.tmp_path = Path(self.tmp_dir.name) if rank == 0 else None
            return self.comm.bcast(self.tmp_path, root=0)

    def __exit__(self, ex_type, ex_value, traceback):
        from mpi4py import MPI
        if self.comm != MPI.COMM_NULL: # TODO DEL once non-participating rank do not participate in fixtures either
            self.comm.barrier()
            if self.comm.rank == 0:
                self.tmp_dir.cleanup()


@pytest.fixture
def mpi_tmpdir(comm):
    '''
    This function ensure that one process handles the naming of temporary folders.
    '''
    with CollectiveTemporaryDirectory(comm) as tmpdir:
        yield tmpdir
