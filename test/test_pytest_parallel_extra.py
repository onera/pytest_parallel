"""
  This module tests extra facilities of the plugin so the core plugin
  can be used to set up the test framework (we suppose that the core
  plugin is correct because it has been tested before)
"""
import pytest
import pytest_parallel

from pytest_parallel.plugin import collective_tmp_dir


@pytest_parallel.mark.parallel(3)
def test_collective_tmp_dir(comm):
  with collective_tmp_dir(comm) as tmpdir:
    assert tmpdir.exists() and tmpdir.is_dir() # Check dir has been created
    assert comm.allgather(tmpdir) == comm.Get_size() * [tmpdir]  # Check if path is the same across all ranks

  comm.barrier() # Wait for suppression
  assert not tmpdir.exists()
