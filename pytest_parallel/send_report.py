import argparse
import socket
import pickle
from pathlib import Path
from _pytest._code.code import (
    ExceptionChainRepr,
    ReprTraceback,
    ReprEntryNative,
)
from .utils.socket import send as socket_send


parser = argparse.ArgumentParser(description='Send return the codes of the tests to the master pytest_parallel process')

parser.add_argument('--_scheduler_ip_address', dest='_scheduler_ip_address', type=str)
parser.add_argument('--_scheduler_port', dest='_scheduler_port', type=int)
parser.add_argument('--_session_folder', dest='_session_folder', type=str)
parser.add_argument('--_test_idx', dest='_test_idx', type=int)
parser.add_argument('--_test_name', dest='_test_name', type=str)

args = parser.parse_args()

def _file_path(when):
    return Path(f'.pytest_parallel/{args._session_folder}/_partial/{args._test_idx}_{when}')

def _longrepr_from_str(msg):
    trace_back = ReprTraceback([ReprEntryNative(msg)], None, None)
    collect_longrepr = []
    collect_longrepr.append(
        (trace_back, None, None)
    )
    return ExceptionChainRepr(collect_longrepr)


def _fill_test_info_from_report(test_info, when):
    assert when in ['setup', 'call', 'teardown']

    file_path = _file_path(when)
    if file_path.exists():
        try:
            with open(file_path, 'rb') as file:
                report_info = file.read()
                report_info = pickle.loads(report_info)
                test_info[when] = report_info
            failed = report_info['outcome'] == 'failed'
        except pickle.PickleError:
            test_info['fatal_error'] = f'FATAL ERROR in pytest_parallel : unable to decode {file_path}'
            failed = True
    else: # Supposedly not found because the test crashed before writing the file
        msg = f'Error: the test crashed during `{when}` phase. '
        red = 31
        bold = 1
        msg = f'\x1b[{red}m' + f'\x1b[{bold}m' + msg+ '\x1b[0m'
        msg += f'Log file: {args._test_name}\n'
        longrepr = _longrepr_from_str(msg)

        test_info[when] = {'outcome' : 'failed',
                           'longrepr': longrepr,
                           'duration': 0, } # unable to report accurately

        failed = True
    return failed

def _retrieve_test_info():
    test_info = {'test_idx': args._test_idx, 'fatal_error': None} # TODO no fatal_error=None (absense means no error)
    for when in ('setup', 'call', 'teardown'):
        test_info[when] = {'outcome' : 'passed',
                           'longrepr': _longrepr_from_str(''),
                           'duration': 0, }

    # During test execution, the following files are created in order:
    # 1. before_import
    # 2. collect
    # 3. pre_run_error
    # 4. setup
    # 5. call
    # 6. teardown
    # if one of the file is missing, it means there was a crash (except for `pre_run_error`, where it is the other way around)
      
    # 1. if `before_import` is not present, we crashed at the very begining
    if not _file_path('before_import').exists():
        test_info['fatal_error']  = 'FATAL ERROR in pytest_parallel early processing\n'
        test_info['fatal_error'] += f'Log file: {args._test_name}\n'
        return test_info

    # 2. handle collection
    if not _file_path('collect').exists(): # if `collect` is not present, we crashed during the test collection
        test_info['fatal_error']  = 'FATAL ERROR in pytest_parallel during test collection\n'
        test_info['fatal_error'] += f'Log file: {args._test_name}\n'
        return test_info
    else: # else we report if the collection failed
        with open(_file_path('collect'), 'rb') as file:
            report_info = file.read()
            report_info = pickle.loads(report_info)
            if report_info['outcome'] == 'failed':
                # Note:
                #   We could send report_info['longrepr'] to master so that it reports it directly
                #   However, it would be confusing, because master also did the collection phase with no error
                #   (if there were an error, the worker would not run in the first place)
                #   To make it clear that the error appears on the worker only, better refer to the report of the worker
                msg = f'Error: the test crashed during `collect` phase. '
                red = 31
                bold = 1
                msg = f'\x1b[{red}m' + f'\x1b[{bold}m' + msg+ '\x1b[0m'
                msg += f'Log file: {args._test_name}\n'
                longrepr = _longrepr_from_str(msg)

                # report as a setup failure (because indeed, the worker failed to setup the test by failing to collect it)
                test_info['setup'] = {'outcome' : 'failed',
                                      'longrepr': longrepr,
                                      'duration': 0, } # unable to report accurately
                return test_info

    # 3. if `pre_run_error` is present, there was a fatal error in the pytest_parallel test handling
    file_path = _file_path('pre_run_error')
    if file_path.exists():
        with open(file_path, 'r', encoding='utf-8') as file:
            pre_run_error_msg = file.read()
            test_info['fatal_error'] = pre_run_error_msg
        return test_info

    # 4.,5.,6.: 'setup/call/teardown' files
    for when in ('setup', 'call', 'teardown'):
        failed = _fill_test_info_from_report(test_info, when)
        if failed:
            return test_info

    return test_info




test_info = _retrieve_test_info()

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((args._scheduler_ip_address, args._scheduler_port))
    socket_send(s, pickle.dumps(test_info))
