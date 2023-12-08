import socket
#from socket_utils import send
import socket_utils
import subprocess
import datetime

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
    #p = subprocess.Popen([f'python3 -u worker.py {port} {i} > out.txt 2> err.txt'], shell=True)
    print('starting subprocess - ',datetime.datetime.now())
    p = subprocess.Popen([f'srun --exclusive --ntasks=1 --qos c1_inter_giga -l python3 -u worker.py {port} {i} > out_{i}.txt 2> err_{i}.txt'], shell=True) # --exclusive for SLURM to parallelize with srun (https://stackoverflow.com/a/66805905/1583122)
    print('detached subprocess - ',datetime.datetime.now())
    workers.append(p)

  # recv worker messages
  remaining_workers = n
  while n>0:
    print(f'remaining_workers={n} - ',datetime.datetime.now())
    conn, addr = s.accept()
    with conn:
      msg = socket_utils.recv(conn)
      print(msg)
    n -= 1

  # wait for workers to finish and collect error codes
  returncodes = []
  for p in workers:
    print('wait to finish - ',datetime.datetime.now())
    returncode = p.wait()
    returncodes.append(returncode)
