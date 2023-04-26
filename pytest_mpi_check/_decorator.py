import pytest


def mark_mpi_test(n_proc_list):
    if isinstance(n_proc_list, int):
        n_proc_list = [n_proc_list]  # One integer `i` is considered equivalent to `[i]`

    def parallel_impl(tested_fun):
        return pytest.mark.parametrize("sub_comm", n_proc_list, indirect=["sub_comm"])(
            (tested_fun)
        )

    return parallel_impl
