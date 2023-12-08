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
srun --exclusive --ntasks=2 -l python3 -u ~/dev/pytest_parallel/slurm/worker.py 10.33.240.8 35403 0 > out_0.txt 2> err_0.txt &
srun --exclusive --ntasks=2 -l python3 -u ~/dev/pytest_parallel/slurm/worker.py 10.33.240.8 35403 1 > out_1.txt 2> err_1.txt &

wait
