def send(sock, msg):
  msg_bytes = msg.encode('utf-8')

  msg_len = len(msg_bytes)
  sent = sock.send(msg_len.to_bytes(4,'big')) # send int64 big endian
  if sent == 0:
    raise RuntimeError('Socket send broken: could not send message size')

  totalsent = 0
  while totalsent < msg_len:
    sent = sock.send(msg_bytes[totalsent:])
    if sent == 0:
      raise RuntimeError('Socket send broken: could not send message')
    totalsent = totalsent + sent

def recv(sock):
  msg_len_bytes = sock.recv(4)
  if msg_len_bytes == b'':
    raise RuntimeError('Socket recv broken: no message size')
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
  return msg_bytes.decode('utf-8')
