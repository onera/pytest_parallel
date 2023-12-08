#!/bin/bash

#SBATCH --job-name=pytest_par
#SBATCH --time 00:30:00
#SBATCH --qos=co_short_std
#SBATCH --ntasks=88
#SBATCH --nodes=2-2
#SBATCH --output=slurm.%j.out
#SBATCH --error=slurm.%j.err

whoami
echo "before 88"
srun --exclusive --ntasks=88 -l hostname &
echo "after 88"
wait
echo "after wait"
nproc --all
