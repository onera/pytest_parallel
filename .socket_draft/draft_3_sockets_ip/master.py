import socket
import socket_utils
import subprocess

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    # setup master's socket
    ip, port = socket_utils.setup_socket(s)
    print(f'socket ip={ip}, port={port}')

    print('waiting for socket connection')
    conn, addr = s.accept()
    with conn:
      print(f"Connected by {addr}")
      msg = socket_utils.recv(conn)
      print(msg)
