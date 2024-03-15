#!/bin/bash

#SBATCH --job-name=pytest_par
#SBATCH --time 00:30:00
#SBATCH --qos=co_short_std
#SBATCH --ntasks=4
##SBATCH --nodes=2-2
#SBATCH --nodes=1-1
#SBATCH --output=slurm.%j.out
#SBATCH --error=slurm.%j.err

#source /scratchm/sonics/dist/source.sh --env maia --compiler gcc@12 --mpi intel-oneapi
module load socle-cfd/6.0-intel2220-impi
export PYTHONPATH=/stck/bberthou/dev/pytest_parallel:$PYTHONPATH
export PYTEST_PLUGINS=pytest_parallel.plugin
srun --exclusive --ntasks=2 -l python3 -u -m pytest --scheduler=slurm --max_n_proc=4 -vv -s --color=yes test/pytest_parallel_tests/test_two_success_fail_tests_two_procs.py --_worker --_scheduler_ip_address=10.33.240.8 --_scheduler_port=56851 --_test_idx=0 > out_0.txt 2> err_0.txt &
srun --exclusive --ntasks=2 -l python3 -u -m pytest --scheduler=slurm --max_n_proc=4 -vv -s --color=yes test/pytest_parallel_tests/test_two_success_fail_tests_two_procs.py --_worker --_scheduler_ip_address=10.33.240.8 --_scheduler_port=56851 --_test_idx=1 > out_1.txt 2> err_1.txt &

wait
