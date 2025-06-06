import os
import stat
import subprocess
import socket
import pickle
from pathlib import Path

import pytest
from mpi4py import MPI

from .utils.socket import recv as socket_recv
from .utils.socket import setup_socket
from .utils.items import add_n_procs, run_item_test, mark_original_index, mark_skip
from .utils.file import remove_exotic_chars, create_folders
from .static_scheduler_utils import group_items_by_parallel_steps
from .exception import PytestParallelEnvError

def mpi_command(current_proc, n_proc):
    mpi_vendor = MPI.get_vendor()[0]
    if mpi_vendor == 'Intel MPI':
        cmd =  f'I_MPI_PIN_PROCESSOR_LIST={current_proc}-{current_proc+n_proc-1}; '
        cmd += f'mpiexec -np {n_proc}'
        return cmd
    elif mpi_vendor == 'Open MPI':
        cores = ','.join([str(i) for i in range(current_proc,current_proc+n_proc)])
        return f'mpiexec --cpu-list {cores} -np {n_proc}'
    else:
        assert 0, f'Unknown MPI implementation "{mpi_vendor}"'

def submit_items(items_to_run, SCHEDULER_IP_ADDRESS, port, session_folder, main_invoke_params, i_step, n_step):
    # sort item by comm size to launch bigger first (Note: in case SLURM prioritize first-received items)
    items = sorted(items_to_run, key=lambda item: item.n_proc, reverse=True)

    # launch `mpiexec` for each item
    script_prolog = ''
    script_prolog += '#!/bin/bash\n\n'

    socket_flags=f"--_scheduler_ip_address={SCHEDULER_IP_ADDRESS} --_scheduler_port={port} --_session_folder={session_folder}"
    cmds = []
    current_proc = 0
    for item in items:
        test_idx = item.original_index
        test_out_file = f'.pytest_parallel/{session_folder}/{remove_exotic_chars(item.nodeid)}'
        test_out_file = str(Path(test_out_file).absolute()) # easier to find the file if absolute
        cmd = '('
        cmd += mpi_command(current_proc, item.n_proc)
        cmd += f' python3 -u -m pytest -s --_worker {socket_flags} {main_invoke_params} --_test_idx={test_idx} {item.config.rootpath}/{item.nodeid}'
        cmd += f' > {test_out_file} 2>&1'
        cmd += f' ; python3 -m pytest_parallel.send_report {socket_flags} --_test_idx={test_idx} --_test_name={test_out_file}'
        cmd += ')'
        cmds.append(cmd)
        current_proc += item.n_proc

    # create the script
    ## 1. prolog
    script = script_prolog

    ## 2. join all the commands
    ##   '&' makes it work in parallel (the following commands does not wait for the previous ones to finish)
    ##   '\' (escaped with '\\') makes it possible to use multiple lines
    script += ' & \\\n'.join(cmds) + '\n'

    ## 3. wait everyone
    script += '\nwait\n'

    script_path = f'.pytest_parallel/{session_folder}/pytest_static_sched_{i_step+1}.sh'
    with open(script_path,'w', encoding='utf-8') as f:
        f.write(script)

    current_permissions = stat.S_IMODE(os.lstat(script_path).st_mode)
    os.chmod(script_path, current_permissions | stat.S_IXUSR)

    #p = subprocess.Popen([script_path], shell=True, stdout=subprocess.PIPE)
    p = subprocess.Popen([script_path], shell=True)
    print(f'\nLaunching tests (step {i_step+1}/{n_step})...')
    return p

def receive_items(items, session, socket, n_item_to_recv):
    # > Precondition: Items must keep their original order to pick up the right item at the reception
    original_indices = [item.original_index for item in items]
    assert original_indices==list(range(len(items)))

    while n_item_to_recv>0:
        conn, _ = socket.accept()
        with conn:
            msg = socket_recv(conn)
        test_info = pickle.loads(msg) # the worker is supposed to have send a dict with the correct structured information
        if 'signal_info' in test_info:
            print('signal_info= ',test_info['signal_info'])
            break
        else:
            test_idx = test_info['test_idx']
            if test_info['fatal_error'] is not None:
                assert 0, f'{test_info["fatal_error"]}'
            item = items[test_idx] # works because of precondition
            item.sub_comm = None
            item.info = test_info

            # "run" the test (i.e. trigger PyTest pipeline but do not really run the code)
            nextitem = None  # not known at this point
            run_item_test(item, nextitem, session)
            n_item_to_recv -= 1

class ShellStaticScheduler:
    def __init__(self, main_invoke_params, ntasks, detach):
        self.main_invoke_params = main_invoke_params
        self.ntasks             = ntasks
        self.detach             = detach

        self.socket             = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # TODO close at the end

        # Check that MPI can be called in a subprocess (not the case with OpenMPI 4.0.5, see #17)
        p = subprocess.run('mpirun -np 1 echo mpi_can_be_called_from_subprocess', shell=True)
        if p.returncode != 0:
            raise PytestParallelEnvError(
                "Your MPI implementation does not handle MPI being called from a sub-process\n"
                "Either update your MPI version or use another scheduler. See https://github.com/onera/pytest_parallel/issues/17"
            )

    @pytest.hookimpl(tryfirst=True)
    def pytest_pyfunc_call(self, pyfuncitem):
        # This is where the test is normally run.
        # Since the scheduler process only collects the reports, it needs to *not* run anything
        # (except skipped tests, which are not really run)
        if not (hasattr(pyfuncitem, "marker_mpi_skip") and pyfuncitem.marker_mpi_skip):
            return True  # for this hook, `firstresult=True` so returning a non-None will stop other hooks to run

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtestloop(self, session) -> bool:
        # same beginning as PyTest default's
        if (
            session.testsfailed
            and not session.config.option.continue_on_collection_errors
        ):
            raise session.Interrupted(
                f"{session.testsfailed} error{'s' if session.testsfailed != 1 else ''} during collection"
            )

        if session.config.option.collectonly:
            return True

        # mark original position
        mark_original_index(session.items)
        ## add proc to items
        add_n_procs(session.items)

        items_by_steps, items_to_skip = group_items_by_parallel_steps(session.items, self.ntasks)

        # run skipped
        for i, item in enumerate(items_to_skip):
            item.sub_comm = None
            mark_skip(item, self.ntasks)
            nextitem = items_to_skip[i + 1] if i + 1 < len(items_to_skip) else None
            run_item_test(item, nextitem, session)

        # schedule tests to run
        SCHEDULER_IP_ADDRESS, port = setup_socket(self.socket)
        session_folder = create_folders()
        n_step = len(items_by_steps)
        for i_step,items in enumerate(items_by_steps):
            n_item_to_receive = len(items)
            sub_process = submit_items(items, SCHEDULER_IP_ADDRESS, port, session_folder, self.main_invoke_params, i_step, n_step)
            if not self.detach: # The job steps are supposed to send their reports
                receive_items(session.items, session, self.socket, n_item_to_receive)
            returncode = sub_process.wait() # at this point, the sub-process should be done since items have been received

            # https://docs.pytest.org/en/stable/reference/exit-codes.html
            # 0 means all passed, 1 means all executed, but some failed
            assert returncode==0 or returncode==1 , f'Pytest internal error during step {i_step} of shell scheduler (error code {returncode})'

        return True

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item):
        """
        Need to hook to pass the test sub-comm and the master_running_proc to `pytest_runtest_logreport`,
        and for that we add the sub-comm to the only argument of `pytest_runtest_logreport`, that is, `report`
        Also, if test is not run on this proc, mark the outcome accordingly
        """
        result = yield
        report = result.get_result()
        if hasattr(item, "marker_mpi_skip") and item.marker_mpi_skip:
            report.mpi_skip = True
        else:
            report.info = item.info

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_logreport(self, report):
        if hasattr(report, "mpi_skip") and report.mpi_skip:
            pass
        else:
            assert report.when in ("setup", "call", "teardown")  # only known tags

            report.outcome  = report.info[report.when]['outcome']
            report.longrepr = report.info[report.when]['longrepr']
            report.duration = report.info[report.when]['duration']
