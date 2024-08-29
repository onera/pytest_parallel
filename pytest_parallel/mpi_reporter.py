import numpy as np
import pytest
from mpi4py import MPI

from .algo import partition, lower_bound
from .utils import get_n_proc_for_test, add_n_procs, run_item_test, mark_original_index
from .utils_mpi import number_of_working_processes, is_dyn_master_process
from .gather_report import gather_report_on_local_rank_0


def mark_skip(item):
    comm = MPI.COMM_WORLD
    n_rank = comm.Get_size()
    n_proc_test = get_n_proc_for_test(item)
    skip_msg = f"Not enough procs to execute: {n_proc_test} required but only {n_rank} available"
    item.add_marker(pytest.mark.skip(reason=skip_msg), append=False)
    item.marker_mpi_skip = True


def sub_comm_from_ranks(global_comm, sub_ranks):
    group = global_comm.group
    sub_group = group.Incl(sub_ranks)
    sub_comm = global_comm.Create_group(sub_group)
    return sub_comm

def create_sub_comm_of_size(global_comm, n_proc, mpi_comm_creation_function):
    if mpi_comm_creation_function == 'MPI_Comm_create':
        return sub_comm_from_ranks(global_comm, range(0,n_proc))
    elif mpi_comm_creation_function == 'MPI_Comm_split':
        if i_rank < n_proc_test:
            color = 1
        else:
            color = MPI.UNDEFINED
        return global_comm.Split(color, key=i_rank)
    else:
        assert 0, 'Unknown MPI communicator creation function. Available: `MPI_Comm_create`, `MPI_Comm_split`'

def create_sub_comms_for_each_size(global_comm, mpi_comm_creation_function):
    i_rank = global_comm.Get_rank()
    n_rank = global_comm.Get_size()
    sub_comms = [None] * n_rank
    for i in range(0,n_rank):
        n_proc = i+1
        sub_comms[i] = create_sub_comm_of_size(global_comm, n_proc, mpi_comm_creation_function)
    return sub_comms


def add_sub_comm(items, global_comm, test_comm_creation, mpi_comm_creation_function):
    i_rank = global_comm.Get_rank()
    n_rank = global_comm.Get_size()

    # Strategy 'by_rank': create one sub-communicator by size, from sequential (size=1) to n_rank
    if test_comm_creation == 'by_rank':
        sub_comms = create_sub_comms_for_each_size(global_comm, mpi_comm_creation_function)
    # Strategy 'by_test': create one sub-communicator per test (do not reuse communicators between tests
    ## Note: the sub-comms are created below (inside the item loop)

    for item in items:
        n_proc_test = get_n_proc_for_test(item)

        if n_proc_test > n_rank:  # not enough procs: mark as to be skipped
            mark_skip(item)
            item.sub_comm = MPI.COMM_NULL
        else:
            if test_comm_creation == 'by_rank':
                item.sub_comm = sub_comms[n_proc_test-1]
            elif test_comm_creation == 'by_test':
                item.sub_comm = create_sub_comm_of_size(global_comm, n_proc_test, mpi_comm_creation_function)
            else:
                assert 0, 'Unknown test MPI communicator creation strategy. Available: `by_rank`, `by_test`'

class SequentialScheduler:
    def __init__(self, global_comm, test_comm_creation='by_rank', mpi_comm_creation_function='MPI_Comm_create', barrier_at_test_start=True, barrier_at_test_end=True):
        self.global_comm = global_comm.Dup()  # ensure that all communications within the framework are private to the framework
        self.test_comm_creation = test_comm_creation
        self.mpi_comm_creation_function = mpi_comm_creation_function
        self.barrier_at_test_start = barrier_at_test_start
        self.barrier_at_test_end   = barrier_at_test_end

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(self, config, items):
        add_sub_comm(items, self.global_comm, self.test_comm_creation, self.mpi_comm_creation_function)

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_runtest_protocol(self, item, nextitem):
        if self.barrier_at_test_start:
            self.global_comm.barrier()
        #print(f'pytest_runtest_protocol beg {MPI.COMM_WORLD.rank=}')
        _ = yield
        #print(f'pytest_runtest_protocol end {MPI.COMM_WORLD.rank=}')
        if self.barrier_at_test_end:
            self.global_comm.barrier()

    #@pytest.hookimpl(tryfirst=True)
    #def pytest_runtest_protocol(self, item, nextitem):
    #    if self.barrier_at_test_start:
    #        self.global_comm.barrier()
    #    print(f'pytest_runtest_protocol beg {MPI.COMM_WORLD.rank=}')
    #    if item.sub_comm == MPI.COMM_NULL:
    #        return True # for this hook, `firstresult=True` so returning a non-None will stop other hooks to run

    @pytest.hookimpl(tryfirst=True)
    def pytest_pyfunc_call(self, pyfuncitem):
        #print(f'pytest_pyfunc_call {MPI.COMM_WORLD.rank=}')
        # This is where the test is normally run.
        # Only run the test for the ranks that do participate in the test
        if pyfuncitem.sub_comm == MPI.COMM_NULL:
            return True # for this hook, `firstresult=True` so returning a non-None will stop other hooks to run

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
        if report.sub_comm != MPI.COMM_NULL:
            gather_report_on_local_rank_0(report)
        else:
            return True # ranks that don't participate in the tests don't have to report anything


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
        self.global_comm = global_comm.Dup()  # ensure that all communications within the framework are private to the framework

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
                report.duration = mpi_report.duration


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
                report.duration = mpi_report.duration
