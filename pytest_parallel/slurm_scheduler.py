import pytest
import subprocess
import socket
import pickle
from pathlib import Path
from .utils.socket import recv as socket_recv
from .utils.socket import setup_socket
from .utils.items import get_n_proc_for_test, add_n_procs, run_item_test, mark_original_index, mark_skip
from .utils.file import remove_exotic_chars, create_folders
from .algo import partition

def submit_items(items_to_run, socket, session_folder, main_invoke_params, ntasks, slurm_conf):
    SCHEDULER_IP_ADDRESS, port = setup_socket(socket)

    # generate SLURM header options
    if slurm_conf['file'] is not None:
        with open(slurm_conf['file']) as f:
            slurm_header = f.read()
        # Note: 
        #    ntasks is supposed to be <= to the number of the ntasks submitted to slurm
        #    but since the header file can be arbitrary, we have no way to check at this point
    else:
        slurm_header  = '#!/bin/bash\n'
        slurm_header += '\n'
        slurm_header += '#SBATCH --job-name=pytest_parallel\n'
        slurm_header += f'#SBATCH --output=.pytest_parallel/{session_folder}/slurm.out\n'
        slurm_header += f'#SBATCH --error=.pytest_parallel/{session_folder}/slurm.err\n'
        for opt in slurm_conf['options']:
            slurm_header += f'#SBATCH {opt}\n'
        slurm_header += f'#SBATCH --ntasks={ntasks}'

    # sort item by comm size to launch bigger first (Note: in case SLURM prioritize first-received items)
    items = sorted(items_to_run, key=lambda item: item.n_proc, reverse=True)

    # launch srun for each item
    srun_options = slurm_conf['srun_options']
    if srun_options is None:
      srun_options = ''
    socket_flags = f"--_scheduler_ip_address={SCHEDULER_IP_ADDRESS} --_scheduler_port={port} --_session_folder={session_folder}"
    cmds = ''
    if slurm_conf['init_cmds'] is not None:
        cmds += slurm_conf['init_cmds'] + '\n'
    for item in items:
        test_idx = item.original_index
        test_out_file = f'.pytest_parallel/{session_folder}/{remove_exotic_chars(item.nodeid)}'
        cmd = '('
        cmd += f'srun {srun_options}'
        cmd +=  ' --exclusive'
        cmd +=  ' --kill-on-bad-exit=1' # make fatal errors (e.g. segfault) kill the whole srun step. Else, deadlock (at least with Intel MPI)
        cmd += f' --ntasks={item.n_proc}'
        cmd +=  ' -l' # 
        cmd += f' python3 -u -m pytest -s --_worker {socket_flags} {main_invoke_params} --_test_idx={test_idx} {item.config.rootpath}/{item.nodeid}'
        cmd += f' > {test_out_file} 2>&1'
        cmd += f' ; python3 -m pytest_parallel.send_report {socket_flags} --_test_idx={test_idx} --_test_name={test_out_file}'
        cmd +=  ')'
        cmd +=  ' &\n' # launch everything in parallel
        cmds += cmd
    cmds += 'wait\n'

    job_cmds = f'{slurm_header}\n\n{cmds}'

    with open(f'.pytest_parallel/{session_folder}/job.sh','w') as f:
      f.write(job_cmds)

    # submit SLURM job
    with open(f'.pytest_parallel/{session_folder}/env_vars.sh','wb') as f:
      f.write(pytest._pytest_parallel_env_vars)

    if slurm_conf['export_env']:
        sbatch_cmd = f'sbatch --parsable --export-file=.pytest_parallel/{session_folder}/env_vars.sh .pytest_parallel/{session_folder}/job.sh'
    else:
        sbatch_cmd = f'sbatch --parsable .pytest_parallel/{session_folder}/job.sh'

    p = subprocess.Popen([sbatch_cmd], shell=True, stdout=subprocess.PIPE)
    print('\nSubmitting tests to SLURM...')
    returncode = p.wait()
    assert returncode==0, f'Error when submitting to SLURM with `{sbatch_cmd}`'

    slurm_job_id = int(p.stdout.read())

    print(f'SLURM job {slurm_job_id} has been submitted')
    return slurm_job_id

def receive_items(items, session, socket, n_item_to_recv):
    while n_item_to_recv>0:
        conn, addr = socket.accept()
        with conn:
            msg = socket_recv(conn)
        test_info = pickle.loads(msg) # the worker is supposed to have send a dict with the correct structured information
        test_idx = test_info['test_idx']
        if test_info['fatal_error'] is not None:
            assert 0, f'{test_info["fatal_error"]}'
        item = items[test_idx]
        item.sub_comm = None
        item.info = test_info

        # "run" the test (i.e. trigger PyTest pipeline but do not really run the code)
        nextitem = None  # not known at this point
        run_item_test(items[test_idx], nextitem, session)
        n_item_to_recv -= 1

class SlurmScheduler:
    def __init__(self, main_invoke_params, ntasks, slurm_conf, detach):
        self.main_invoke_params = main_invoke_params
        self.ntasks             = ntasks
        self.detach             = detach

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # TODO close at the end

        self.slurm_conf         = slurm_conf
        self.slurm_job_id = None

    @pytest.hookimpl(tryfirst=True)
    def pytest_pyfunc_call(self, pyfuncitem):
        # This is where the test is normally run.
        # Since the scheduler process only collects the reports, it needs to *not* run anything.
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
                "%d error%s during collection"
                % (session.testsfailed, "s" if session.testsfailed != 1 else "")
            )

        if session.config.option.collectonly:
            return True

        # mark original position
        mark_original_index(session.items)
        ## add proc to items
        add_n_procs(session.items)

        # isolate skips
        has_enough_procs = lambda item: item.n_proc <= self.ntasks
        items_to_run, items_to_skip = partition(session.items, has_enough_procs)

        # run skipped
        for i, item in enumerate(items_to_skip):
            item.sub_comm = None
            mark_skip(item, self.ntasks)
            nextitem = items_to_skip[i + 1] if i + 1 < len(items_to_skip) else None
            run_item_test(item, nextitem, session)

        # schedule tests to run
        n_item_to_receive = len(items_to_run)
        if n_item_to_receive > 0:
          session_folder = create_folders()
          self.slurm_job_id = submit_items(items_to_run, self.socket, session_folder, self.main_invoke_params, self.ntasks, self.slurm_conf)
          if not self.detach: # The job steps are supposed to send their reports
              receive_items(session.items, session, self.socket, n_item_to_receive)

        return True

    @pytest.hookimpl()
    def pytest_keyboard_interrupt(excinfo):
        if excinfo.slurm_job_id is not None:
            print(f'Calling `scancel {excinfo.slurm_job_id}`')
            subprocess.run(['scancel',str(excinfo.slurm_job_id)])

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
