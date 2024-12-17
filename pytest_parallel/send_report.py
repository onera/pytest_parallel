import argparse
import socket
import pickle
from . import socket_utils
from _pytest._code.code import (
    ExceptionChainRepr,
    ReprTraceback,
    ReprEntryNative,
    ReprFileLocation,
)

#print("toto")

parser = argparse.ArgumentParser(description='Send return the codes of the tests to the master pytest_parallel process')

parser.add_argument('--_scheduler_ip_address', dest='_scheduler_ip_address', type=str, help='Internal pytest_parallel option')
parser.add_argument('--_scheduler_port', dest='_scheduler_port', type=int, help='Internal pytest_parallel option')
parser.add_argument('--_test_idx', dest='_test_idx', type=int, help='Internal pytest_parallel option')

args = parser.parse_args()
#print(args._scheduler_ip_address)
#print(args._scheduler_port)
#print(args._test_idx)

#with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
#  s.connect((args._scheduler_ip_address, args._scheduler_port))
#  print(f'{test_info=}')

test_info = {'test_idx': args._test_idx, 'fatal_error': None} # TODO no fatal_error=None (absense means no error)

# "fatal_error" named file
try:
  file_path = f'.pytest_parallel/{args._test_idx}_fatal_error'
  with open(file_path, "r") as file:
    fatal_error = file.read()
    test_info['fatal_error'] = fatal_error
except FileNotFoundError: # There was no fatal error file, i.e. no fatal error
  pass

# "setup/call/teardown" named pipes
for report_when in ("setup", "call", "teardown"):
  try:
    file_path = f'.pytest_parallel/{args._test_idx}_{report_when}'
    #print('file_path = ',file_path)
    with open(file_path, "rb") as file:
      report_info = file.read()
      report_info = pickle.loads(report_info)
      test_info[report_when] = report_info
  except FileNotFoundError: # Supposedly not found because the test crashed before without creating and writing to the file
    collect_longrepr = []
    msg = f"PROCESS killed"
    full_msg = f"\n-------------------------------- {msg} --------------------------------"
    fake_trace_back = ReprTraceback([ReprEntryNative(full_msg)], None, None)
    collect_longrepr.append(
        (fake_trace_back, None, None)
    )
    longrepr = ExceptionChainRepr(collect_longrepr)

    test_info[report_when] = {'outcome' : "failed",
                              'longrepr': longrepr,
                              'duration': 0, } # unable to report accurately
  except pickle.PickleError:
    test_info['fatal_error'] = f'FATAL ERROR in pytest_parallel : unable to read {file_path}'


#print("#"*100)
#print(test_info)
#print("#"*100)
#print("\n\n\n")

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
  s.connect((args._scheduler_ip_address, args._scheduler_port))
  socket_utils.send(s, pickle.dumps(test_info))

