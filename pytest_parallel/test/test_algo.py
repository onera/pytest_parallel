from pytest_parallel import algo


def less_than(k):
    def partial_less_than(i):
        return i < k

    return partial_less_than


def test_partition():
    samples = [10, 2, 3, 5, 6, 3, 1, 7]
    assert algo.partition(samples, less_than(5)) == ([2, 3, 3, 1], [10, 5, 6, 7])

    samples = [10]
    assert algo.partition(samples, less_than(5)) == ([], [10])

    samples = [1]
    assert algo.partition(samples, less_than(5)) == ([1], [])

    samples = []
    assert algo.partition(samples, less_than(5)) == ([], [])


def test_partition_point_basic():
    def identity(x):
        return x

    samples = [True, True, False]
    # samples[2] is the first False element
    assert algo.partition_point(samples, identity) == 2

    samples = [True, True, True]
    assert algo.partition_point(samples, identity) == 3

    samples = [False, False, False]
    assert algo.partition_point(samples, identity) == 0

    samples = []
    assert algo.partition_point(samples, identity) == 0


def test_partition_point():
    samples = [0, 1, 2, 3, 4, 5, 6]
    # indices  0, 1, 2, 3, 4, 5, 6

    # first element i for which i<3 becomes false (i.e. i==3) is at position 3
    assert algo.partition_point(samples, less_than(3)) == 3

    # more tests
    assert algo.partition_point(samples, less_than(-1)) == 0

    assert algo.partition_point(samples, less_than(0)) == 0
    assert algo.partition_point(samples, less_than(6)) == 6

    assert algo.partition_point(samples, less_than(7)) == 7
    assert algo.partition_point(samples, less_than(8)) == 7


def test_lower_bound():
    samples = [0, 1, 1, 2, 2, 2, 3]
    # indices  0, 1, 2, 3, 4, 5, 6

    # first element i where i<2 becomes false (i.e. i==2) is at position 3
    assert algo.lower_bound(samples, 2) == 3

    # more tests
    assert algo.lower_bound(samples, -1) == 0
    assert algo.lower_bound(samples, 0) == 0
    assert algo.lower_bound(samples, 1) == 1
    assert algo.lower_bound(samples, 3) == 6
    assert algo.lower_bound(samples, 4) == 7

    # other array
    samples = [0, 1, 3]
    # first element i where i<2 becomes false (i.e. i==3) is at position 2
    assert algo.lower_bound(samples, 2) == 2


def test_upper_bound():
    samples = [0, 1, 1, 2, 2, 2, 3]
    # indices  0, 1, 2, 3, 4, 5, 6

    # first element i where i>2 is true (i.e. i==3) is at position 6
    assert algo.upper_bound(samples, 2) == 6

    # more tests
    assert algo.lower_bound(samples, -1) == 0
    assert algo.lower_bound(samples, 0) == 0
    assert algo.lower_bound(samples, 1) == 1
    assert algo.lower_bound(samples, 3) == 6
    assert algo.lower_bound(samples, 4) == 7

    # other array
    samples = [0, 1, 3]
    # first element i where i>2 is true (i.e. i==3) is at position 2
    assert algo.lower_bound(samples, 2) == 2
