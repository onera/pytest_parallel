import socket
import socket_utils
import time
import sys
import datetime
from mpi4py import MPI

assert len(sys.argv) == 4
scheduler_ip = sys.argv[1]
server_port = int(sys.argv[2])
test_idx = int(sys.argv[3])

comm = MPI.COMM_WORLD
print(f'start at {scheduler_ip}@{server_port} test {test_idx} at rank {comm.Get_rank()}/{comm.Get_size()} exec on {socket.gethostname()} - ',datetime.datetime.now())

if comm.Get_rank() == 0:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((scheduler_ip, server_port))
        #time.sleep(10+5*test_idx)
        #msg = f'Hello from test {test_idx} at rank {comm.Get_rank()}/{comm.Get_size()} exec on {socket.gethostname()}'
        #socket_utils.send(s, msg)
        info = {
            'test_idx': test_idx,
            'setup': {
                'outcome': 'passed',
                'longrepr': 'setup msg',
            },
            'call': {
                'outcome': 'passed',
                'longrepr': 'call msg',
            },
            'teardown': {
                'outcome': 'passed',
                'longrepr': 'teardown msg',
            },
        }
        socket_utils.send(s, str(info))
