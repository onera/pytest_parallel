import socket
import socket_utils
import time

from machine_conf import ip, port

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((ip, port))
    socket_utils.send(s, f'Hello from {socket.gethostname()}')
    time.sleep(2)
