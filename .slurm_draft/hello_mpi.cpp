#include "mpi.h"
#include <iostream>

int main(int argc, char *argv[]) {
  MPI_Init(&argc, &argv);

  int world_size;
  MPI_Comm_size(MPI_COMM_WORLD, &world_size);
  int rank;
  MPI_Comm_rank(MPI_COMM_WORLD, &rank);
  std::cout << "mpi proc = " << rank << "/" << world_size << "\n";

  MPI_Finalize();

  return 0;
}
