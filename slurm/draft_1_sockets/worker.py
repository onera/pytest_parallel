import socket
import socket_utils
#import time
import sys

LOCALHOST = '127.0.0.1'

assert len(sys.argv) == 3
server_port = int(sys.argv[1])
test_idx = int(sys.argv[2])

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
  s.connect((LOCALHOST, server_port))
  socket_utils.send(s, f'Hello from {test_idx}')
