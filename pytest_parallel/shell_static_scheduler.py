import pytest
import os
import shutil
import stat
import subprocess
import socket
import pickle
from pathlib import Path
from . import socket_utils
from .utils import get_n_proc_for_test, add_n_procs, run_item_test, mark_original_index
from .algo import partition
from .static_scheduler_utils import group_items_by_parallel_steps
from mpi4py import MPI
import numpy as np

def mark_skip(item, ntasks):
    n_proc_test = get_n_proc_for_test(item)
    skip_msg = f"Not enough procs to execute: {n_proc_test} required but only {ntasks} available"
    item.add_marker(pytest.mark.skip(reason=skip_msg), append=False)
    item.marker_mpi_skip = True

def replace_sub_strings(s, subs, replacement):
  res = s
  for sub in subs:
    res = res.replace(sub,replacement)
  return res

def remove_exotic_chars(s):
  return replace_sub_strings(str(s), ['[',']','/', ':'], '_')

def parse_job_id_from_submission_output(s):
    # At this point, we are trying to guess -_-
    # Here we supposed that the command for submitting the job
    #    returned string with only one number,
    #    and that this number is the job id
    import re
    return int(re.search(r'\d+', str(s)).group())


# https://stackoverflow.com/a/34177358
def command_exists(cmd_name):
    """Check whether `name` is on PATH and marked as executable."""
    return shutil.which(cmd_name) is not None

def _get_my_ip_address():
  hostname = socket.gethostname()

  assert command_exists('tracepath'), 'pytest_parallel SLURM scheduler: command `tracepath` is not available'
  cmd = ['tracepath','-4','-n',hostname]
  r = subprocess.run(cmd, stdout=subprocess.PIPE)
  assert r.returncode==0, f'pytest_parallel SLURM scheduler: error running command `{" ".join(cmd)}`'
  ips = r.stdout.decode("utf-8")

  try:
    my_ip = ips.split('\n')[0].split(':')[1].split()[0]
  except:
    assert 0, f'pytest_parallel SLURM scheduler: error parsing result `{ips}` of command `{" ".join(cmd)}`'
  import ipaddress
  try:
    ipaddress.ip_address(my_ip)
  except ValueError:
    assert 0, f'pytest_parallel SLURM scheduler: error parsing result `{ips}` of command `{" ".join(cmd)}`'

  return my_ip

def setup_socket(socket):
    # Find IP our address
    SCHEDULER_IP_ADDRESS = _get_my_ip_address()

    # setup master's socket
    socket.bind((SCHEDULER_IP_ADDRESS, 0)) # 0: let the OS choose an available port
    socket.listen()
    port = socket.getsockname()[1]
    return SCHEDULER_IP_ADDRESS, port

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

def submit_items(items_to_run, SCHEDULER_IP_ADDRESS, port, main_invoke_params, ntasks, i_step, n_step):
    # sort item by comm size to launch bigger first (Note: in case SLURM prioritize first-received items)
    items = sorted(items_to_run, key=lambda item: item.n_proc, reverse=True)

    # launch `mpiexec` for each item
    script_prolog = ''
    script_prolog += '#!/bin/bash\n\n'
    #script_prolog += 'return_codes=(' + ' '.join(['0'*len(items)]) + ')\n\n' # bash array that will contain the return codes of each test TODO DEL

    socket_flags=f"--_scheduler_ip_address={SCHEDULER_IP_ADDRESS} --_scheduler_port={port}"
    cmds = []
    current_proc = 0
    for i,item in enumerate(items):
        test_idx = item.original_index
        test_out_file = f'.pytest_parallel/{remove_exotic_chars(item.nodeid)}'
        cmd = '('
        cmd += mpi_command(current_proc, item.n_proc)
        cmd += f' python3 -u -m pytest -s --_worker {socket_flags} {main_invoke_params} --_test_idx={test_idx} {item.config.rootpath}/{item.nodeid}'
        cmd += f' > {test_out_file} 2>&1'
        cmd += f' ; python -m pytest_parallel.send_report {socket_flags} --_test_idx={test_idx} --_test_name={test_out_file}'
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

    # TODO DEL
    ## 4. send error codes to to the server
    #script += f'\npython -m pytest_parallel.send_return_codes {socket_flags} --return_codes=\"' + '${return_codes[@]}' + '\"\n'

   
    Path('.pytest_parallel').mkdir(exist_ok=True)
    shutil.rmtree('.pytest_parallel/tmp', ignore_errors=True)
    Path('.pytest_parallel/tmp').mkdir()
    script_path = f'.pytest_parallel/pytest_static_sched_{i_step+1}.sh'
    #print('script_path  = ',script_path)
    #print('sscript= ',script)
    with open(script_path,'w') as f:
      f.write(script)

    current_permissions = stat.S_IMODE(os.lstat(script_path).st_mode)
    os.chmod(script_path, current_permissions | stat.S_IXUSR)

    #p = subprocess.Popen([script_path], shell=True, stdout=subprocess.PIPE)
    p = subprocess.Popen([script_path], shell=True)
    print(f'\nLaunching tests (step {i_step+1}/{n_step})...')
    return p

def receive_items(items, session, socket, n_item_to_recv):
    # > Precondition: Items must keep their original order to pick up the right item at the reception
    original_indices = np.array([item.original_index for item in items])
    assert (original_indices==np.arange(len(items))).all()

    while n_item_to_recv>0:
        conn, addr = socket.accept()
        with conn:
            msg = socket_utils.recv(conn)
        test_info = pickle.loads(msg) # the worker is supposed to have send a dict with the correct structured information
        #print(f"{test_info=}")
        if 'signal_info' in test_info:
            print('signal_info= ',test_info['signal_info'])
            break;
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
                "%d error%s during collection"
                % (session.testsfailed, "s" if session.testsfailed != 1 else "")
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
        SCHEDULER_IP_ADDRESS,port = setup_socket(self.socket)
        n_step = len(items_by_steps)
        for i_step,items in enumerate(items_by_steps):
            n_item_to_receive = len(items)
            sub_process = submit_items(items, SCHEDULER_IP_ADDRESS, port, self.main_invoke_params, self.ntasks, i_step, n_step)
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
