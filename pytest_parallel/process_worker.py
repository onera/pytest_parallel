import pytest

from mpi4py import MPI

import socket
import pickle
from . import socket_utils
from .utils import get_n_proc_for_test, run_item_test
from .gather_report import gather_report_on_local_rank_0

class ProcessWorker:
    def __init__(self, scheduler_ip_address, scheduler_port, test_idx, detach):
        self.scheduler_ip_address = scheduler_ip_address
        self.scheduler_port = scheduler_port
        self.test_idx = test_idx
        self.detach = detach

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtestloop(self, session) -> bool:
        comm = MPI.COMM_WORLD
        print("\n\n\nwololo",[item.name for item in session.items])
        assert len(session.items) == 1, f'INTERNAL FATAL ERROR in pytest_parallel with slurm scheduling: should only have one test per worker, but got {len(session.items)}'
        item = session.items[0]
        test_comm_size = get_n_proc_for_test(item)

        item.sub_comm = comm
        item.test_info = {'test_idx': self.test_idx, 'fatal_error': None}


        if comm.Get_size() != test_comm_size: # fatal error, SLURM and MPI do not interoperate correctly
            error_info = f'FATAL ERROR in pytest_parallel with slurm scheduling: test `{item.nodeid}`' \
                         f' uses a `comm` of size {test_comm_size} but was launched with size {comm.Get_size()}.\n' \
                         f' This generally indicates that `srun` does not interoperate correctly with MPI.'

            item.test_info['fatal_error'] = error_info
        else: # normal case: the test can be run
            nextitem = None
            run_item_test(item, nextitem, session)

        if not self.detach and comm.Get_rank() == 0: # not detached: proc 0 is expected to send results to scheduling process
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.scheduler_ip_address, self.scheduler_port))
                socket_utils.send(s, pickle.dumps(item.test_info))

        if item.test_info['fatal_error'] is not None:
            assert 0, f'{item.test_info["fatal_error"]}'

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
        report.test_info.update({report.when: {'outcome' : report.outcome,
                                               'longrepr': report.longrepr,
                                               'duration': report.duration, }})


