import socket
import socket_utils
import time

# TODO replace by what master.py actually printed
ip = '172.20.0.37'
port = 46031

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((ip, port))
    socket_utils.send(s, f'Hello from {socket.gethostname()}')
    time.sleep(2)
