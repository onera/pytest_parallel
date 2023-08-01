"""
  This module tests extra facilities of the plugin so the core plugin
  can be used to set up the test framework (we suppose that the core
  plugin is correct because it has been tested before)
"""
import pytest_parallel

from pytest_parallel.plugin import CollectiveTemporaryDirectory


@pytest_parallel.mark.parallel(3)
def test_collective_tmpdir_00(comm):
    with CollectiveTemporaryDirectory(comm) as tmpdir:
        assert tmpdir.exists() and tmpdir.is_dir()  # Check dir has been created
        assert comm.allgather(tmpdir) == comm.Get_size() * [
            tmpdir
        ]  # Check if path is the same across all ranks

    comm.barrier()  # Wait for suppression
    assert not tmpdir.exists()


@pytest_parallel.mark.parallel(3)
def test_collective_tmpdir_01(comm, mpi_tmpdir):
    assert mpi_tmpdir.exists() and mpi_tmpdir.is_dir()  # Check dir has been created
    assert comm.allgather(mpi_tmpdir) == comm.Get_size() * [
        mpi_tmpdir
    ]  # Check if path is the same across all ranks
