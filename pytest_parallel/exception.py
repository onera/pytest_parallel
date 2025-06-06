
def _to_bold_red(s):
  red = '\x1b[31m'
  bold = '\x1b[1m'
  reset = '\x1b[0m'
  return red + bold + s + reset

class PytestParallelInternalError(Exception):
  def __init__(self, msg):
    Exception.__init__(self, _to_bold_red('pytest_parallel internal error')+'\n' + msg)

class PytestParallelUsageError(Exception):
  def __init__(self, msg):
    Exception.__init__(self, _to_bold_red('You are calling pytest_parallel incorrectly')+'\n' + msg)

class PytestParallelEnvError(Exception):
  def __init__(self, msg):
    Exception.__init__(self, _to_bold_red('pytest_parallel environment error:')+'\n' + msg)
