#!/bin/bash
#MSUB -r deploy_test
#MSUB -o sonics.out
#MSUB -e sonics.err
#MSUB -n 1
#MSUB -T 1600
#MSUB -A
####MSUB -x
#MSUB -q milan
#MSUB -Q test
#MSUB -m scratch,work

hostname -I
python worker.py
