import subprocess

print('master begin')
p = subprocess.Popen(['python -u worker.py > out.txt 2> err.txt'], shell=True)
# worker.py is launched asynchronously
print('master end')
# master.py will finish quickly (not waiting worker.py to finish)
# However, worker.py will still continue until it is done
