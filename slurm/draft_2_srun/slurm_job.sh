#!/bin/bash

#SBATCH --job-name=pytest_par
#SBATCH --time 00:30:00
#SBATCH --qos=co_short_std
#SBATCH --ntasks=88
#SBATCH --nodes=2-2
#SBATCH --output=slurm.%j.out
#SBATCH --error=slurm.%j.err

#date
#source /scratchm/sonics/dist/2023-11/source.sh --env sonics_dev --compiler gcc@12 --mpi intel-oneapi

date
#./master_1p.sh
#./master_1p_no_exclusive.sh
./master_multi_node.sh
date
