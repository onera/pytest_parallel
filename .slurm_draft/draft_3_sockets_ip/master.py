import socket
#from socket_utils import send
import socket_utils
import subprocess

ips = ['127.0.0.1']
#ips = ['10.33.240.8','125.1.42.8','125.1.5.200','10.33.224.8']
#ips = ['125.1.5.200','10.33.224.8']
port = 10000

for i,ip in enumerate(ips):
  with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    # setup master's socket
    s.bind((ip, port+i)) # port=0: let the OS choose an available port
    s.listen()
    port = s.getsockname()[1]

    conn, addr = s.accept()
    with conn:
      print(f"Connected by {addr}")
      msg = socket_utils.recv(conn)
      print(msg)
