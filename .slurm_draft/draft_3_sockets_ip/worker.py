import socket
import socket_utils
import time
#import time
#import sys

ips = ['127.0.0.1']
#ips = ['10.33.240.8','125.1.42.8','125.1.5.200','10.33.224.8']
#ips = ['125.1.5.200','10.33.224.8']
port = 10000

for i,ip in enumerate(ips):
  print(i)
  with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((ip, port+i))
    socket_utils.send(s, f'Hello from {socket.gethostname()} at {i}')
  time.sleep(2)
