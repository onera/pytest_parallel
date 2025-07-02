from pathlib import Path
import pickle

import pytest
from mpi4py import MPI

from .utils.items import get_n_proc_for_test, run_item_test
from .gather_report import gather_report_on_local_rank_0

class ProcessWorker:
    def __init__(self, scheduler_ip_address, scheduler_port, session_folder, test_idx, detach):
        self.scheduler_ip_address = scheduler_ip_address
        self.scheduler_port = scheduler_port
        self.session_folder = session_folder
        self.test_idx = test_idx
        self.detach = detach


    def _file_path(self, when):
        return Path(f'.pytest_parallel/{self.session_folder}/_partial/{self.test_idx}_{when}')

    @pytest.hookimpl(tryfirst=True)
    def pytest_make_collect_report(self, collector):
        comm = MPI.COMM_WORLD

        # Here, we are just before the call to the `pytest_make_collect_report` function of pytest
        # The pytest `pytest_make_collect_report` function is the one that imports the test,
        # So it is possible that it crashes (e.g. forced exit in a module imported by the test).
        # Hence, before calling it, we want to register the fact that we at least reached this point
        if comm.rank == 0:
            file_path = self._file_path('before_import')
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('before import')

    @pytest.hookimpl(tryfirst=True)
    def pytest_collectreport(self, report):
        comm = MPI.COMM_WORLD

        if comm.rank == 0:
            collect_file = self._file_path('collect')

            # For an unknown reason, `pytest_collectreport` is called several times
            # However, we only use one 'collect' file
            # So we need to create the file if it is has not been created yet
            # If the file already exists, then we overwrite it if it previously passed and we now fail
            if not collect_file.exists():
                do_report = True
            else:
              with open(collect_file, 'rb') as file:
                  previous_report_info = file.read()
                  previous_report_info = pickle.loads(previous_report_info)
                  if previous_report_info['outcome'] == 'passed' and report.outcome == 'failed':
                      do_report = True
                  else:
                      do_report = False

            if do_report:
                report_info = {'outcome' : report.outcome,
                               'longrepr': report.longrepr,
                               'duration': 0., }
                with open(collect_file, 'wb') as f:
                    f.write(pickle.dumps(report_info))


    @pytest.hookimpl(tryfirst=True)
    def pytest_runtestloop(self, session) -> bool:
        comm = MPI.COMM_WORLD
        assert len(session.items) == 1, f'INTERNAL FATAL ERROR in pytest_parallel with slurm scheduling: should only have one test per worker, but got {len(session.items)}'
        item = session.items[0]
        test_comm_size = get_n_proc_for_test(item)

        item.sub_comm = comm
        item.test_info = {'test_idx': self.test_idx, 'fatal_error': None} # TODO 2025-07 not used, remove


        # check there is no file from a previous run # TODO move this check up the pytest workflow, and complete it with other files
        if comm.rank == 0:
            for when in ['pre_run_error', 'setup', 'call', 'teardown']:
                path = self._file_path(when)
                assert not path.exists(), f'INTERNAL FATAL ERROR in pytest_parallel: file "{path}" should not exist at this point'

        # check the number of procs matches the one specified by the test
        if comm.size != test_comm_size: # fatal error, SLURM and MPI do not interoperate correctly
            if comm.rank == 0:
                error_info = f'FATAL ERROR in pytest_parallel with slurm scheduling: test `{item.nodeid}`' \
                             f' uses a `comm` of size {test_comm_size} but was launched with size {comm.size}.\n' \
                             f' This generally indicates that `srun` does not interoperate correctly with MPI.'
                file_path = self._file_path('pre_run_error')
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(error_info)
            return True

        # run the test
        nextitem = None
        run_item_test(item, nextitem, session)

        # TODO 2025-07 not used, remove
        if item.test_info['fatal_error'] is not None:
            assert 0, f'{item.test_info["fatal_error"]}'

        return True

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item):
        """
        We need to hook to pass the test sub-comm to `pytest_runtest_logreport`,
        and for that we add the sub-comm to the only argument of `pytest_runtest_logreport`, that is, `report`
        We also need to pass `item.test_info` so that we can update it # TODO 2025-07 not used, remove
        """
        result = yield
        report = result.get_result()
        report.sub_comm = item.sub_comm
        report.test_info = item.test_info # TODO 2025-07 not used, remove

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_logreport(self, report):
        assert report.when in ("setup", "call", "teardown")  # only known tags
        sub_comm = report.sub_comm # keep `sub_comm` because `gather_report_on_local_rank_0` removes it
        gather_report_on_local_rank_0(report)
        report_info = {'outcome' : report.outcome,
                       'longrepr': report.longrepr,
                       'duration': report.duration, }
        if sub_comm.rank == 0:
            with open(self._file_path(report.when), 'wb') as f:
                f.write(pickle.dumps(report_info))
