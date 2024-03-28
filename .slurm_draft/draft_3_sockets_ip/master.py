import socket
#from socket_utils import send
import socket_utils
import subprocess
from machine_conf import ip, port

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    # setup master's socket
    s.bind((ip, port)) # port=0: let the OS choose an available port
    s.listen()
    port = s.getsockname()[1]

    print('waiting for socket connection')
    conn, addr = s.accept()
    with conn:
      print(f"Connected by {addr}")
      msg = socket_utils.recv(conn)
      print(msg)
