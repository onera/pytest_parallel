import socket
#from socket_utils import send
import socket_utils
import subprocess

LOCALHOST = '127.0.0.1'

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
  # setup master's socket
  s.bind((LOCALHOST, 0)) # 0: let the OS choose an available port
  s.listen()
  port = s.getsockname()[1]

  n = 4

  # launch workers
  workers = []
  for i in range(0,n):
    p = subprocess.Popen([f'python -u worker.py {port} {i} > out.txt 2> err.txt'], shell=True)
    workers.append(p)

  # recv worker messages
  remaining_workers = n
  while n>0:
    conn, addr = s.accept()
    with conn:
      print(f"Connected by {addr}")
      msg = socket_utils.recv(conn)
      print(msg)
    n -= 1

  # wait for workers to finish and collect error codes
  returncodes = []
  for p in workers:
    returncode = p.wait()
    returncodes.append(returncode)
