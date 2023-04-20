import re

regex = '(?=.*A\n)(?=.*B\n).*'

strings = [
  'A\n B\n',
  'B\n A\n',
  'A\n',
]
for s in strings:
  print(repr(s))
  print(re.findall(regex, s, flags=re.DOTALL))
  print('\n')
