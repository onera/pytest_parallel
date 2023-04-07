import re

regex = '(?=.*A\n)(?=.*B\n).*'

results = [
  'A\n B\n',
  'B\n A\n',
  'A\n',
]
for result in results:
  print(repr(result))
  print(re.findall(regex, result,flags=re.DOTALL))
  print('\n')
