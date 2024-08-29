import pytest
import subprocess
import socket
import pickle
from pathlib import Path
from . import socket_utils
from .utils import get_n_proc_for_test, add_n_procs, run_item_test, mark_original_index
from .algo import partition


def mark_skip(item, slurm_ntasks):
    n_proc_test = get_n_proc_for_test(item)
    skip_msg = f"Not enough procs to execute: {n_proc_test} required but only {slurm_ntasks} available"
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
    from shutil import which
    return which(cmd_name) is not None

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


def submit_items(items_to_run, socket, main_invoke_params, slurm_ntasks, slurm_conf):
    # Find IP our address
    SCHEDULER_IP_ADDRESS = _get_my_ip_address()

    # setup master's socket
    socket.bind((SCHEDULER_IP_ADDRESS, 0)) # 0: let the OS choose an available port
    socket.listen()
    port = socket.getsockname()[1]

    # generate SLURM header options
    if slurm_conf['file'] is not None:
        with open(slurm_conf['file']) as f:
            slurm_header = f.read()
        # Note: 
        #    slurm_ntasks is supposed to be <= to the number of the ntasks submitted to slurm
        #    but since the header file can be arbitrary, we have no way to check at this point
    else:
        slurm_header  = '#!/bin/bash\n'
        slurm_header += '\n'
        slurm_header += '#SBATCH --job-name=pytest_parallel\n'
        slurm_header += '#SBATCH --output=pytest_slurm/slurm.%j.out\n'
        slurm_header += '#SBATCH --error=pytest_slurm/slurm.%j.err\n'
        for opt in slurm_conf['options']:
            slurm_header += f'#SBATCH {opt}\n'
        slurm_header += f'#SBATCH --ntasks={slurm_ntasks}'

    # sort item by comm size to launch bigger first (Note: in case SLURM prioritize first-received items)
    items = sorted(items_to_run, key=lambda item: item.n_proc, reverse=True)

    # launch srun for each item
    worker_flags=f"--_worker --_scheduler_ip_address={SCHEDULER_IP_ADDRESS} --_scheduler_port={port}"
    cmds = ''
    if slurm_conf['additional_cmds'] is not None:
        cmds += slurm_conf['additional_cmds'] + '\n'
    for item in items:
        test_idx = item.original_index
        test_out_file_base = f'pytest_slurm/{remove_exotic_chars(item.nodeid)}'
        cmd =  f'srun --exclusive --ntasks={item.n_proc} -l'
        cmd += f' python3 -u -m pytest -s {worker_flags} {main_invoke_params} --_test_idx={test_idx} {item.config.rootpath}/{item.nodeid}'
        cmd += f' > {test_out_file_base} 2>&1'
        cmd += ' &\n' # launch everything in parallel
        cmds += cmd
    cmds += 'wait\n'

    pytest_slurm = f'{slurm_header}\n\n{cmds}'
    Path('pytest_slurm').mkdir(exist_ok=True)
    with open('pytest_slurm/job.sh','w') as f:
      f.write(pytest_slurm)

    # submit SLURM job
    with open('pytest_slurm/env_vars.sh','wb') as f:
      f.write(pytest._pytest_parallel_env_vars)

    if slurm_conf['sub_command'] is None:
        if slurm_conf['export_env']:
            sbatch_cmd = 'sbatch --parsable --export-file=pytest_slurm/env_vars.sh pytest_slurm/job.sh'
        else:
            sbatch_cmd = 'sbatch --parsable pytest_slurm/job.sh'
    else:
        sbatch_cmd = slurm_conf['sub_command'] + ' pytest_slurm/job.sh'

    p = subprocess.Popen([sbatch_cmd], shell=True, stdout=subprocess.PIPE)
    print('\nSubmitting tests to SLURM...')
    returncode = p.wait()
    assert returncode==0, f'Error when submitting to SLURM with `{sbatch_cmd}`'

    if slurm_conf['sub_command'] is None:
        slurm_job_id = int(p.stdout.read())
    else:
        slurm_job_id = parse_job_id_from_submission_output(p.stdout.read())

    print(f'SLURM job {slurm_job_id} has been submitted')
    return slurm_job_id

def receive_items(items, session, socket, n_item_to_recv):
    while n_item_to_recv>0:
        conn, addr = socket.accept()
        with conn:
            msg = socket_utils.recv(conn)
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

class ProcessScheduler:
    def __init__(self, main_invoke_params, slurm_ntasks, slurm_conf, detach):
        self.main_invoke_params    = main_invoke_params
        self.slurm_ntasks          = slurm_ntasks
        self.slurm_conf            = slurm_conf
        self.detach                = detach

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # TODO close at the end
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
        has_enough_procs = lambda item: item.n_proc <= self.slurm_ntasks
        items_to_run, items_to_skip = partition(session.items, has_enough_procs)

        # run skipped
        for i, item in enumerate(items_to_skip):
            item.sub_comm = None
            mark_skip(item, self.slurm_ntasks)
            nextitem = items_to_skip[i + 1] if i + 1 < len(items_to_skip) else None
            run_item_test(item, nextitem, session)

        # schedule tests to run
        n_item_to_receive = len(items_to_run)
        if n_item_to_receive > 0:
          self.slurm_job_id = submit_items(items_to_run, self.socket, self.main_invoke_params, self.slurm_ntasks, self.slurm_conf)
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
