import argparse
import socket
import pickle
from pathlib import Path
from .utils.socket import send as socket_send
from _pytest._code.code import (
    ExceptionChainRepr,
    ReprTraceback,
    ReprEntryNative,
)


parser = argparse.ArgumentParser(description='Send return the codes of the tests to the master pytest_parallel process')

parser.add_argument('--_scheduler_ip_address', dest='_scheduler_ip_address', type=str)
parser.add_argument('--_scheduler_port', dest='_scheduler_port', type=int)
parser.add_argument('--_session_folder', dest='_session_folder', type=str)
parser.add_argument('--_test_idx', dest='_test_idx', type=int)
parser.add_argument('--_test_name', dest='_test_name', type=str)

args = parser.parse_args()

def _file_path(when):
  return Path(f'.pytest_parallel/{args._session_folder}/_partial/{args._test_idx}_{when}')

test_info = {'test_idx': args._test_idx, 'fatal_error': None} # TODO no fatal_error=None (absense means no error)

# 'fatal_error' file
file_path = _file_path('fatal_error')
if file_path.exists():
  with open(file_path, 'r') as file:
    fatal_error = file.read()
    test_info['fatal_error'] = fatal_error


# 'setup/call/teardown' files
already_failed = False
for when in ('setup', 'call', 'teardown'):
  file_path = _file_path(when)
  if file_path.exists():
    try:
      with open(file_path, 'rb') as file:
        report_info = file.read()
        report_info = pickle.loads(report_info)
        test_info[when] = report_info
    except pickle.PickleError:
      test_info['fatal_error'] = f'FATAL ERROR in pytest_parallel : unable to decode {file_path}'
  else: # Supposedly not found because the test crashed before writing the file
    collect_longrepr = []
    msg = f'Error: the test crashed. '
    red = 31
    bold = 1
    msg = f'\x1b[{red}m' + f'\x1b[{bold}m' + msg+ '\x1b[0m'
    msg += f'Log file: {args._test_name}\n'
    trace_back = ReprTraceback([ReprEntryNative(msg)], None, None)
    collect_longrepr.append(
        (trace_back, None, None)
    )
    longrepr = ExceptionChainRepr(collect_longrepr)
    
    outcome = 'passed' if already_failed else 'failed' # No need to report the error twice
    test_info[when] = {'outcome' : outcome,
                       'longrepr': longrepr,
                       'duration': 0, } # unable to report accurately

    already_failed = True


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
  s.connect((args._scheduler_ip_address, args._scheduler_port))
  socket_send(s, pickle.dumps(test_info))

