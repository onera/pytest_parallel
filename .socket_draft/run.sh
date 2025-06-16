#!/bin/bash

#SBATCH --job-name=pytest_par
#SBATCH --time 00:30:00
#SBATCH --qos=co_short_std
#SBATCH --ntasks=1
##SBATCH --nodes=2-2
#SBATCH --output=slurm.%j.out
#SBATCH --error=slurm.%j.err

#echo $TOTO
whoami
#srun --exclusive --ntasks=1 -l hostname
nproc --all
