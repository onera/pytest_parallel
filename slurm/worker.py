import socket
import socket_utils
import time
import sys
import datetime

LOCALHOST = '127.0.0.1'

assert len(sys.argv) == 3
server_port = int(sys.argv[1])
test_idx = int(sys.argv[2])

print(f'start proc {test_idx} - ',datetime.datetime.now())

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
  time.sleep(10)
  s.connect((LOCALHOST, server_port))
  socket_utils.send(s, f'Hello from {test_idx}')
