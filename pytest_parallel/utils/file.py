from pathlib import Path
import tempfile

def replace_sub_strings(s, subs, replacement):
  res = s
  for sub in subs:
    res = res.replace(sub,replacement)
  return res

def remove_exotic_chars(s):
  return replace_sub_strings(str(s), ['[',']','/', ':'], '_')


def create_folders():
  Path('.pytest_parallel').mkdir(exist_ok=True)
  session_folder_abs = Path(tempfile.mkdtemp(dir='.pytest_parallel'))
  Path(session_folder_abs/'_partial').mkdir()
  return session_folder_abs.name
