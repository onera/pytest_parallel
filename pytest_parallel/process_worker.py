import pytest

from mpi4py import MPI

from pathlib import Path
import pickle
from .utils import get_n_proc_for_test, run_item_test
from .gather_report import gather_report_on_local_rank_0

class ProcessWorker:
    def __init__(self, scheduler_ip_address, scheduler_port, test_idx, detach):
        self.scheduler_ip_address = scheduler_ip_address
        self.scheduler_port = scheduler_port
        self.test_idx = test_idx
        self.detach = detach


    def _file_path(self, when):
        return Path(f'.pytest_parallel/tmp/{self.test_idx}_{when}')

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtestloop(self, session) -> bool:
        comm = MPI.COMM_WORLD
        assert len(session.items) == 1, f'INTERNAL FATAL ERROR in pytest_parallel with slurm scheduling: should only have one test per worker, but got {len(session.items)}'
        item = session.items[0]
        test_comm_size = get_n_proc_for_test(item)

        item.sub_comm = comm
        item.test_info = {'test_idx': self.test_idx, 'fatal_error': None}


        # remove previous file if they existed
        if comm.rank == 0:
            for when in {'fatal_error', 'setup', 'call', 'teardown'}:
                path = self._file_path(when)
                if path.exists():
                    path.unlink()

        if comm.size != test_comm_size: # fatal error, SLURM and MPI do not interoperate correctly
            if comm.rank == 0:
                error_info = f'FATAL ERROR in pytest_parallel with slurm scheduling: test `{item.nodeid}`' \
                             f' uses a `comm` of size {test_comm_size} but was launched with size {comm.Get_size()}.\n' \
                             f' This generally indicates that `srun` does not interoperate correctly with MPI.'
                file_path = self._file_path('fatal_error')
                with open(file_path, "w") as f:
                    f.write(error_info)
            return True

        # run the test
        nextitem = None
        run_item_test(item, nextitem, session)

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
        sub_comm = report.sub_comm # keep `sub_comm` because `gather_report_on_local_rank_0` removes it
        gather_report_on_local_rank_0(report)
        report_info = {'outcome' : report.outcome,
                       'longrepr': report.longrepr,
                       'duration': report.duration, }
        if sub_comm.rank == 0:
            with open(self._file_path(report.when), "wb") as f:
                f.write(pickle.dumps(report_info))
