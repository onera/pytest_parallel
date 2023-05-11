import pytest


def parallel(n_proc_list):
    """
    @pytest_parallel.mark.parallel([2,3])
    def test_fun(comm):
        pass

    is equivalent to

    `@pytest.mark.parametrize('comm', [2,3], indirect=['comm'])`
    def test_fun(comm):
        pass

    Details
      What is subtle here is that 'comm' means 3 different things
        - the first 'comm' (in `parametrize('comm')`) is a "call_spec"
        - the second 'comm' (in `indirect=['comm']`) is a "fixture",
          which in our case is a function that takes a `request`,
          extracts info from it
          and returns it to the function `test_fun` as a parameter
        - the comm parameter of function `test_fun`, which is the returned value of the fixture
      What happens is that:
        - PyTest will take the "callspec" 'comm' (of value 2 or 3)
        - this will be passed to `pytest_parallel.pytest_collection_modifyitems`
          that will create a communicator
        - we ask for `indirect` because we don't want value 2 or 3 as our 'comm' fixture
          we rather want the communicator created by `pytest_parallel.pytest_collection_modifyitems`
          With `indirect=['comm']`, we tell PyTest to use fixture `comm` to compute the argument
          we want to use in the function body

    """
    if isinstance(n_proc_list, int):
        n_proc_list = [n_proc_list]  # One integer `i` is considered equivalent to `[i]`

    def parallel_impl(tested_fun):
        return pytest.mark.parametrize("comm", n_proc_list, indirect=["comm"])(
            (tested_fun)
        )

    return parallel_impl
