import shutil
import socket
import subprocess

def send(sock, msg_bytes):
  msg_len = len(msg_bytes)
  sent = sock.send(msg_len.to_bytes(8,'big')) # send int64 big endian
  if sent == 0:
    raise RuntimeError('Socket send broken: could not send message size')

  totalsent = 0
  while totalsent < msg_len:
    sent = sock.send(msg_bytes[totalsent:])
    if sent == 0:
      raise RuntimeError('Socket send broken: could not send message')
    totalsent = totalsent + sent

def recv(sock):
  msg_len_bytes = sock.recv(8)
  if msg_len_bytes == b'':
    raise RuntimeError('Socket recv broken: message has no size')
  msg_len = int.from_bytes(msg_len_bytes, 'big') 

  chunks = []
  bytes_recv = 0
  while bytes_recv < msg_len:
    chunk = sock.recv(min(msg_len-bytes_recv, 4096))
    if chunk == b'':
      raise RuntimeError('Socket recv broken: could not receive message')
    chunks.append(chunk)
    bytes_recv += len(chunk)
  msg_bytes = b''.join(chunks)
  return msg_bytes


# https://stackoverflow.com/a/34177358
def command_exists(cmd_name):
    """Check whether `name` is on PATH and marked as executable."""
    return shutil.which(cmd_name) is not None

def _get_my_ip_address():
  hostname = socket.gethostname()

  assert command_exists('tracepath'), 'pytest_parallel SLURM scheduler: command `tracepath` is not available'
  cmd = ['tracepath','-n',hostname]
  r = subprocess.run(cmd, stdout=subprocess.PIPE)
  assert r.returncode==0, f'pytest_parallel SLURM scheduler: error running command `{" ".join(cmd)}`'
  ips = r.stdout.decode("utf-8")

  try:
    my_ip = ips.split('\n')[0].split(':')[1].split()[0]
  except:
    assert 0, f'pytest_parallel SLURM scheduler: error parsing result `{ips}` of command `{" ".join(cmd)}`'
  import ipaddress
  try:
    ipaddress.ip_address(my_ip)
  except ValueError:
    assert 0, f'pytest_parallel SLURM scheduler: error parsing result `{ips}` of command `{" ".join(cmd)}`'

  return my_ip

def setup_socket(socket):
    # Find our IP address
    SCHEDULER_IP_ADDRESS = _get_my_ip_address()

    # setup master's socket
    socket.bind((SCHEDULER_IP_ADDRESS, 0)) # 0: let the OS choose an available port
    socket.listen()
    port = socket.getsockname()[1]
    return SCHEDULER_IP_ADDRESS, port
