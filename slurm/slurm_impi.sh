#!/bin/bash

#SBATCH --job-name=test_slurm_pytest
#SBATCH --ntasks=4
#SBATCH --time 0-0:10
#SBATCH --qos=c1_test_giga
#SBATCH --output=slurm.%j.out
#SBATCH --error=slurm.%j.err

#date
#source /scratchm/sonics/dist/2023-11/source.sh --env sonics_dev --compiler gcc@12 --mpi intel-oneapi

date
python3 master.py
#./master.sh
date
