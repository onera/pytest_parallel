module purge
#module use --append /scratchm/sonics/opt_el8/modules/linux-centos7-broadwell
#module use --append /scratchm/sonics/opt_el8/modules/linux-rhel8-broadwell
#module use --append /scratchm/sonics/usr/modules/
#module load intel-oneapi-mpi-2021.6.0-gcc-8.3.1-hjimxhi
module load impi/.23.2.0
#source /scratchm/sonics/prod/spacky_2022-09-23_el8/external/spack/var/spack/environments/maia_gcc_intel-oneapi_2023-05/loads
#module load intel/23.2.0
#module load gcc/12.1.0
#module load intel/.mkl-2021.2.0
#export I_MPI_CC=$CC
#export I_MPI_CXX=$CXX
#export I_MPI_FC=$FC
#export I_MPI_F90=$FC
##unset I_MPI_PMI_LIBRARY
#echo "CC=$CC"
#echo "CXX=$CXX"
#echo "FC=$FC"
#echo "MPI library: intel-oneapi"
