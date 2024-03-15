import numpy as np
import pytest
from _pytest._code.code import (
    ExceptionChainRepr,
    ReprTraceback,
    ReprEntryNative,
    ReprFileLocation,
)
from mpi4py import MPI

from .algo import partition, lower_bound
from .utils import (
    number_of_working_processes,
    get_n_proc_for_test,
    mark_skip,
    add_n_procs,
    is_dyn_master_process,
)


def gather_report(mpi_reports, n_sub_rank):
    assert len(mpi_reports) == n_sub_rank

    report_init = mpi_reports[0]
    goutcome = report_init.outcome
    glongrepr = report_init.longrepr

    collect_longrepr = []
    # > We need to rebuild a TestReport object, location can be false # TODO ?
    for i_sub_rank, test_report in enumerate(mpi_reports):
        if test_report.outcome == "failed":
            goutcome = "failed"

        if test_report.longrepr:
            msg = f"On rank {i_sub_rank} of {n_sub_rank}"
            full_msg = f"\n-------------------------------- {msg} --------------------------------"
            fake_trace_back = ReprTraceback([ReprEntryNative(full_msg)], None, None)
            collect_longrepr.append(
                (fake_trace_back, ReprFileLocation(*report_init.location), None)
            )
            collect_longrepr.append(
                (test_report.longrepr, ReprFileLocation(*report_init.location), None)
            )

    if len(collect_longrepr) > 0:
        glongrepr = ExceptionChainRepr(collect_longrepr)

    return goutcome, glongrepr


def gather_report_on_local_rank_0(report):
    """
    Gather reports from all procs participating in the test on rank 0 of the sub_comm
    """
    sub_comm = report.sub_comm
    del report.sub_comm  # No need to keep it in the report
    # Furthermore we need to serialize the report
    # and mpi4py does not know how to serialize report.sub_comm
    i_sub_rank = sub_comm.Get_rank()
    n_sub_rank = sub_comm.Get_size()

    if (
        report.outcome != "skipped"
    ):  # Skipped test are only known by proc 0 -> no merge required
        # Warning: PyTest reports can actually be quite big
        request = sub_comm.isend(report, dest=0, tag=i_sub_rank)

        if i_sub_rank == 0:
            mpi_reports = n_sub_rank * [None]
            for _ in range(n_sub_rank):
                status = MPI.Status()

                mpi_report = sub_comm.recv(
                    source=MPI.ANY_SOURCE, tag=MPI.ANY_TAG, status=status
                )
                mpi_reports[status.Get_source()] = mpi_report

            assert (
                None not in mpi_reports
            )  # should have received from all ranks of `sub_comm`
            goutcome, glongrepr = gather_report(mpi_reports, n_sub_rank)

            report.outcome = goutcome
            report.longrepr = glongrepr

        request.wait()

    sub_comm.barrier()


def filter_and_add_sub_comm(items, global_comm):
    i_rank = global_comm.Get_rank()
    n_workers = global_comm.Get_size()

    filtered_items = []
    for item in items:
        n_proc_test = get_n_proc_for_test(item)

        if n_proc_test > n_workers:  # not enough procs: will be skipped
            if global_comm.Get_rank() == 0:
                item.sub_comm = MPI.COMM_SELF
                mark_skip(item)
                filtered_items += [item]
            else:
                item.sub_comm = MPI.COMM_NULL  # TODO this should not be needed
        else:
            if i_rank < n_proc_test:
                color = 1
            else:
                color = MPI.UNDEFINED

            sub_comm = global_comm.Split(color)

            if sub_comm != MPI.COMM_NULL:
                item.sub_comm = sub_comm
                filtered_items += [item]

    return filtered_items


class SequentialScheduler:
    def __init__(self, global_comm):
        self.global_comm = global_comm

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(self, config, items):
        items[:] = filter_and_add_sub_comm(items, self.global_comm)

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_runtestloop(self, session) -> bool:
        _ = yield
        # prevent return value being non-zero (ExitCode.NO_TESTS_COLLECTED)
        # when no test run on non-master
        if self.global_comm.Get_rank() != 0 and session.testscollected == 0:
            session.testscollected = 1
        return True

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item):
        """
        Need to hook to pass the test sub-comm to `pytest_runtest_logreport`,
        and for that we add the sub-comm to the only argument of `pytest_runtest_logreport`, that is, `report`
        """
        result = yield
        report = result.get_result()
        report.sub_comm = item.sub_comm

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_logreport(self, report):
        gather_report_on_local_rank_0(report)


def group_items_by_parallel_steps(items, n_workers):
    add_n_procs(items)
    items.sort(key=lambda item: item.n_proc, reverse=True)

    remaining_n_procs_by_step = []
    items_by_step = []
    items_to_skip = []
    for item in items:
        if item.n_proc > n_workers:
            items_to_skip += [item]
        else:
            found_step = False
            for idx, remaining_procs in enumerate(remaining_n_procs_by_step):
                if item.n_proc <= remaining_procs:
                    items_by_step[idx] += [item]
                    remaining_n_procs_by_step[idx] -= item.n_proc
                    found_step = True
                    break
            if not found_step:
                items_by_step += [[item]]
                remaining_n_procs_by_step += [n_workers - item.n_proc]

    return items_by_step, items_to_skip


def run_item_test(item, nextitem, session):
    item.config.hook.pytest_runtest_protocol(item=item, nextitem=nextitem)
    if session.shouldfail:
        raise session.Failed(session.shouldfail)
    if session.shouldstop:
        raise session.Interrupted(session.shouldstop)


def prepare_items_to_run(items, comm):
    i_rank = comm.Get_rank()

    items_to_run = []

    beg_next_rank = 0
    for item in items:
        n_proc_test = get_n_proc_for_test(item)

        if beg_next_rank <= i_rank < beg_next_rank + n_proc_test:
            color = 1
            items_to_run += [item]
        else:
            color = MPI.UNDEFINED

        comm_split = comm.Split(color)

        item.sub_comm = comm_split
        item.master_running_proc = beg_next_rank
        item.run_on_this_proc = True

        # even for test not run on rank 0, the test must be seen by PyTest
        if i_rank == 0 and item.sub_comm == MPI.COMM_NULL:
            items_to_run += [item]
            item.sub_comm = MPI.COMM_SELF
            item.run_on_this_proc = False

        beg_next_rank += n_proc_test

    return items_to_run


def items_to_run_on_this_proc(items_by_steps, items_to_skip, comm):
    i_rank = comm.Get_rank()

    items = []

    # on rank 0, mark items to skip because not enough procs
    if i_rank == 0:
        for item in items_to_skip:
            item.sub_comm = MPI.COMM_SELF
            item.master_running_proc = 0
            item.run_on_this_proc = True
            mark_skip(item)
        items += items_to_skip

    # distribute items that will really be run
    for items_of_step in items_by_steps:
        items += prepare_items_to_run(items_of_step, comm)

    return items


class StaticScheduler:
    def __init__(self, global_comm):
        self.global_comm = (
            global_comm.Dup()
        )  # ensure that all communications within the framework are private to the framework

    @pytest.hookimpl(tryfirst=True)
    def pytest_pyfunc_call(self, pyfuncitem):
        if not pyfuncitem.run_on_this_proc:
            return True  # for this hook, `firstresult=True` so returning a non-None will stop other hooks to run

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtestloop(self, session) -> bool:
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

        n_workers = self.global_comm.Get_size()

        items_by_steps, items_to_skip = group_items_by_parallel_steps(
            session.items, n_workers
        )

        items = items_to_run_on_this_proc(
            items_by_steps, items_to_skip, self.global_comm
        )

        for i, item in enumerate(items):
            # nextitem = items[i + 1] if i + 1 < len(items) else None
            # For optimization purposes, it would be nice to have the previous commented line
            # (`nextitem` is only used internally by PyTest in _setupstate.teardown_exact)
            # Here, it does not work:
            #   it seems that things are messed up on rank 0
            #   because the nextitem might not be run (see pytest_runtest_setup/call/teardown hooks just above)
            # In practice though, it seems that it is not the main thing that slows things down...

            nextitem = None
            run_item_test(item, nextitem, session)

        # prevent return value being non-zero (ExitCode.NO_TESTS_COLLECTED) when no test run on non-master
        if self.global_comm.Get_rank() != 0 and session.testscollected == 0:
            session.testscollected = 1
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
        report.sub_comm = item.sub_comm
        report.master_running_proc = item.master_running_proc

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_logreport(self, report):
        sub_comm = report.sub_comm
        gather_report_on_local_rank_0(report)

        # master ranks of each sub_comm must send their report to rank 0
        if sub_comm.Get_rank() == 0:  # only master are concerned
            if self.global_comm.Get_rank() != 0:  # if master is not global master, send
                self.global_comm.send(report, dest=0)
            elif report.master_running_proc != 0:  # else, recv if test run remotely
                # In the line below, MPI.ANY_TAG will NOT clash with communications outside the framework because self.global_comm is private
                mpi_report = self.global_comm.recv(
                    source=report.master_running_proc, tag=MPI.ANY_TAG
                )

                report.outcome = mpi_report.outcome
                report.longrepr = mpi_report.longrepr


def sub_comm_from_ranks(global_comm, sub_ranks):
    group = global_comm.group
    sub_group = group.Incl(sub_ranks)
    sub_comm = global_comm.Create_group(sub_group)
    return sub_comm


def item_with_biggest_admissible_n_proc(items, n_av_procs):
    def _key(item):
        return item.n_proc

    # Preconditions:
    #   sorted(items, key)
    #   len(items)>0

    # best choices: tests requiring the most procs while still 'runnable'
    # among those, we favor the first in the array for 'stability' reasons (no reordering when not needed)
    idx = lower_bound(items, n_av_procs, _key)
    if idx == 0 and items[idx].n_proc > n_av_procs:  # all items ask too much
        return -1
    if idx < len(items) and items[idx].n_proc == n_av_procs:
        # we find the first internal item with matching n_proc
        return idx
    # we did not find an item with exactly the matching n_proc,
    # in this case, the item just before gives the new n_proc we are searching for
    max_needed_n_proc = items[idx - 1].n_proc
    return lower_bound(items, max_needed_n_proc, _key)


def mark_original_index(items):
    for i, item in enumerate(items):
        item.original_index = i


########### Client/Server ###########
SCHEDULED_WORK_TAG = 0
WORK_DONE_TAG = 1
REPORT_SETUP_TAG = 2
REPORT_RUN_TAG = 3
REPORT_TEARDOWN_TAG = 4
WHEN_TAGS = {
    "setup": REPORT_SETUP_TAG,
    "call": REPORT_RUN_TAG,
    "teardown": REPORT_TEARDOWN_TAG,
}


####### Server #######
def schedule_test(item, available_procs, inter_comm):
    n_procs = item.n_proc
    original_idx = item.original_index

    sub_ranks = []
    i = 0
    while len(sub_ranks) < n_procs:
        if available_procs[i]:
            sub_ranks.append(i)
        i += 1

    item.sub_ranks = sub_ranks

    # mark the procs as busy
    for sub_rank in sub_ranks:
        available_procs[sub_rank] = False

    # TODO isend would be slightly better (less waiting)
    for sub_rank in sub_ranks:
        inter_comm.send(
            (original_idx, sub_ranks), dest=sub_rank, tag=SCHEDULED_WORK_TAG
        )


def signal_all_done(inter_comm):
    n_workers = number_of_working_processes(inter_comm)
    for i_rank in range(n_workers):
        inter_comm.send((-1, []), dest=i_rank, tag=SCHEDULED_WORK_TAG)


def wait_test_to_complete(items_to_run, session, available_procs, inter_comm):
    # receive from any proc
    status = MPI.Status()
    original_idx = inter_comm.recv(
        source=MPI.ANY_SOURCE, tag=WORK_DONE_TAG, status=status
    )
    first_rank_done = status.Get_source()

    # get associated item
    item = items_to_run[original_idx]
    sub_ranks = item.sub_ranks
    assert first_rank_done in sub_ranks

    # receive done message from all other procs associated to the item
    for sub_rank in sub_ranks:
        if sub_rank != first_rank_done:
            rank_original_idx = inter_comm.recv(source=sub_rank, tag=WORK_DONE_TAG)
            assert (rank_original_idx == original_idx) # sub_rank is supposed to have worked on the same test

    # the procs are now available
    for sub_rank in sub_ranks:
        available_procs[sub_rank] = True

    # "run" the test (i.e. trigger PyTest pipeline but do not really run the code)
    nextitem = None  # not known at this point
    run_item_test(item, nextitem, session)


def wait_last_tests_to_complete(items_to_run, session, available_procs, inter_comm):
    while np.sum(available_procs) < len(available_procs):
        wait_test_to_complete(items_to_run, session, available_procs, inter_comm)


####### Client #######
def receive_run_and_report_tests(
    items_to_run, session, current_item_requests, global_comm, inter_comm
):
    while True:
        # receive
        original_idx, sub_ranks = inter_comm.recv(source=0, tag=SCHEDULED_WORK_TAG)
        if original_idx == -1:
            return # signal work is done

        # run
        sub_comm = sub_comm_from_ranks(global_comm, sub_ranks)
        item = items_to_run[original_idx]
        item.sub_comm = sub_comm
        nextitem = None # not known at this point
        run_item_test(item, nextitem, session)

        # signal work is done for the test
        inter_comm.send(original_idx, dest=0, tag=WORK_DONE_TAG)

        MPI.Request.waitall(current_item_requests) # make sure all report isends have been received
        current_item_requests.clear()


class DynamicScheduler:
    def __init__(self, global_comm, inter_comm):
        self.global_comm = global_comm
        self.inter_comm = inter_comm
        self.current_item_requests = []

    @pytest.hookimpl(tryfirst=True)
    def pytest_pyfunc_call(self, pyfuncitem):
        # This is where the test is normally run.
        # Since the master process only collects the reports, it needs to *not* run anything.
        cond = is_dyn_master_process(self.inter_comm) and not (
            hasattr(pyfuncitem, "marker_mpi_skip") and pyfuncitem.marker_mpi_skip
        )
        if cond:
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

        # parallel algo begin
        n_workers = number_of_working_processes(self.inter_comm)

        ## add proc to items
        add_n_procs(session.items)

        ## isolate skips
        has_enough_procs = lambda item: item.n_proc <= n_workers
        items_to_run, items_to_skip = partition(session.items, has_enough_procs)

        ## remember original position
        #   since every proc is doing that, the original position is the same for all procs
        #   hence, the position can be sent and received among procs: it will lead to the same item
        mark_original_index(items_to_run)

        ## if master proc, schedule
        if is_dyn_master_process(self.inter_comm):
            # mark and run skipped tests
            for i, item in enumerate(items_to_skip):
                item.sub_comm = MPI.COMM_SELF
                mark_skip(item)
                nextitem = items_to_skip[i + 1] if i + 1 < len(items_to_skip) else None
                run_item_test(item, nextitem, session)

            # schedule tests to run
            items_left_to_run = sorted(items_to_run, key=lambda item: item.n_proc)
            available_procs = np.ones(n_workers, dtype=np.int8)

            while len(items_left_to_run) > 0:
                n_av_procs = np.sum(available_procs)

                item_idx = item_with_biggest_admissible_n_proc(items_left_to_run, n_av_procs)

                if item_idx == -1:
                    wait_test_to_complete(items_to_run, session, available_procs, self.inter_comm)
                else:
                    schedule_test(items_left_to_run[item_idx], available_procs, self.inter_comm)
                    del items_left_to_run[item_idx]

            wait_last_tests_to_complete(
                items_to_run, session, available_procs, self.inter_comm
            )
            signal_all_done(self.inter_comm)
        else: # worker proc
            receive_run_and_report_tests(
                items_to_run,
                session,
                self.current_item_requests,
                self.global_comm,
                self.inter_comm,
            )
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
        if is_dyn_master_process(self.inter_comm):
            if hasattr(item, "marker_mpi_skip") and item.marker_mpi_skip:
                report.mpi_skip = True
                report.sub_comm = item.sub_comm
            else:
                report.master_running_proc = item.sub_ranks[0]
        else:
            report.sub_comm = item.sub_comm

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_logreport(self, report):
        if hasattr(report, "mpi_skip") and report.mpi_skip:
            gather_report_on_local_rank_0(
                report
            )  # has been 'run' locally: do nothing special
        else:
            assert report.when in ("setup", "call", "teardown")  # only known tags
            tag = WHEN_TAGS[report.when]

            # master ranks of each sub_comm must send their report to rank 0
            if not is_dyn_master_process(self.inter_comm):
                sub_comm = report.sub_comm
                gather_report_on_local_rank_0(report)

                if sub_comm.Get_rank() == 0:  # if local master proc, send
                    # The idea of the scheduler is the following:
                    #   The server schedules test over clients
                    #   A client executes the test then report to the server it is done
                    #   The server executes the PyTest pipeline to make it think it ran the test (but only receives the reports of the client)
                    #   The server continues its scheduling
                    # Here in the report, we need an isend, because the ordering is the following:
                    #   Client: run test, isend reports, send done to server
                    #   Server: recv done from client, 'run' test (i.e. recv reports)
                    # So the 'send done' must be received before the 'isend report'
                    request = self.inter_comm.isend(report, dest=0, tag=tag)
                    self.current_item_requests.append(request)
            else:  # global master: receive
                mpi_report = self.inter_comm.recv(
                    source=report.master_running_proc, tag=tag
                )

                report.outcome = mpi_report.outcome
                report.longrepr = mpi_report.longrepr


import datetime
import subprocess
import socket
from . import socket_utils

class ProcessWorker:
    def __init__(self, n_working_procs, scheduler_ip_address, scheduler_port, test_idx):
        self.n_working_procs = n_working_procs
        self.scheduler_ip_address = scheduler_ip_address
        self.scheduler_port = scheduler_port
        self.test_idx = test_idx

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtestloop(self, session) -> bool:
        comm = MPI.COMM_WORLD
        print(f'self.test_idx = {self.test_idx}')
        item = session.items[self.test_idx]
        item.sub_comm = comm
        item.test_info = {'test_idx': self.test_idx}
        nextitem = None
        run_item_test(item, nextitem, session)
        print('run_item_test done')
        print(f'item.test_info = {item.test_info}')

        if comm.Get_rank() == 0:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.scheduler_ip_address, self.scheduler_port))
                socket_utils.send(s, str(item.test_info))

        print('sending done')
        return True
      
    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item):
        """
        We need to hook to pass the test sub-comm to `pytest_runtest_logreport`,
        and for that we add the sub-comm to the only argument of `pytest_runtest_logreport`, that is, `report`
        We also need to pass `item.test_info` so that we can update it
        """
        result = yield
        report = result.get_result()
        report.sub_comm = item.sub_comm
        report.test_info = item.test_info

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_logreport(self, report):
        assert report.when in ("setup", "call", "teardown")  # only known tags
        gather_report_on_local_rank_0(report)
        report.test_info.update({report.when: {'outcome': report.outcome, 'longrepr': report.longrepr}})



LOCALHOST = '127.0.0.1'
def submit_items(items_to_run, socket, n_working_procs, main_invoke_params):
    # setup master's socket
    SCHEDULER_IP_ADDRESS='10.33.240.8' # spiro07-clu
    socket.bind((SCHEDULER_IP_ADDRESS, 0)) # 0: let the OS choose an available port
    socket.listen()
    port = socket.getsockname()[1]

    # sort item by comm size
    items = sorted(items_to_run, key=lambda item: item.n_proc, reverse=True)

    # launch srun for each item
    cmds = ''
    for item in items:
        test_idx = item.original_index
        cmd =  f'srun --exclusive --ntasks={item.n_proc} -l'
        cmd += f' python3 -u -m pytest {main_invoke_params}'
        cmd += f' --_worker --_scheduler_ip_address={SCHEDULER_IP_ADDRESS}'
        cmd += f' --_scheduler_port={port} --_test_idx={test_idx}'

        #cmd += f' python3 -u ~/dev/pytest_parallel/slurm/worker.py {SCHEDULER_IP_ADDRESS} {port} {test_idx}'
        cmd += f' > out_{test_idx}.txt 2> err_{test_idx}.txt'
        cmd += ' &' # launch everything in parallel
        cmds += cmd + '\n'

    pytest_slurm = f'''#!/bin/bash

#SBATCH --job-name=pytest_par
#SBATCH --time 00:30:00
#SBATCH --qos=co_short_std
#SBATCH --ntasks={n_working_procs}
##SBATCH --nodes=2-2
#SBATCH --nodes=1-1
#SBATCH --output=slurm.%j.out
#SBATCH --error=slurm.%j.err

#source /scratchm/sonics/dist/source.sh --env maia --compiler gcc@12 --mpi intel-oneapi
module load socle-cfd/6.0-intel2220-impi
export PYTHONPATH=/stck/bberthou/dev/pytest_parallel:$PYTHONPATH
export PYTEST_PLUGINS=pytest_parallel.plugin
{cmds}
wait
'''

    with open('pytest_slurm.sh','w') as f:
      f.write(pytest_slurm)

    ## submit SLURM job
    sbatch_cmd = 'sbatch pytest_slurm.sh'
    p = subprocess.Popen([sbatch_cmd], shell=True)
    print('Submitting tests to SLURM...')
    returncode = p.wait()
    assert returncode==0, f'Error when submitting to SLURM with `{sbatch_cmd}`'

def receive_items(items, session, socket):
    n = len(items)
    #n = 2
    while n>0:
        print(f'remaining_workers={n} - ',datetime.datetime.now())
        conn, addr = socket.accept()
        with conn:
            msg = socket_utils.recv(conn)
            test_info = eval(msg) # the worker is supposed to have send a dict with the correct structured information
            test_idx = test_info['test_idx']
            item = items[test_idx]
            item.sub_comm = MPI.COMM_NULL
            item.info = test_info

            # "run" the test (i.e. trigger PyTest pipeline but do not really run the code)
            nextitem = None  # not known at this point
            run_item_test(items[test_idx], nextitem, session)
        ###    print('run_item_test - done')
        ##test_idx = 2-n
        ##print('run_item_test')
        ##item = items[test_idx]
        ##item.sub_comm = MPI.COMM_NULL
        ##info = {
        ##    'test_idx': test_idx,
        ##    'setup': {
        ##        'outcome': 'passed',
        ##        'longrepr': 'setup msg',
        ##    },
        ##    'call': {
        ##        'outcome': 'passed',
        ##        'longrepr': 'call msg',
        ##    },
        ##    'teardown': {
        ##        'outcome': 'passed',
        ##        'longrepr': 'teardown msg',
        ##    },
        ##}
        ##item.info = info
        ##nextitem = None  # not known at this point
        ##run_item_test(item, nextitem, session) # "run" the test (i.e. trigger PyTest pipeline but do not really run the code)
        ##print('run_item_test - done')
        n -= 1
    print('recv done',datetime.datetime.now())

class ProcessScheduler:
    def __init__(self, n_working_procs, main_invoke_params):
        self.n_working_procs = n_working_procs
        self.current_item_requests = []
        self.main_invoke_params = main_invoke_params
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # TODO close at the end

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
        has_enough_procs = lambda item: item.n_proc <= self.n_working_procs
        items_to_run, items_to_skip = partition(session.items, has_enough_procs)

        # run skipped
        for i, item in enumerate(items_to_skip):
            item.sub_comm = MPI.COMM_SELF
            mark_skip(item)
            nextitem = items_to_skip[i + 1] if i + 1 < len(items_to_skip) else None
            run_item_test(item, nextitem, session)

        # schedule tests to run
        submit_items(items_to_run, self.socket, self.n_working_procs, self.main_invoke_params)
        receive_items(session.items, session, self.socket)

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
