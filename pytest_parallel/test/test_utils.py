from pytest_parallel.mpi_reporter import (
    group_items_by_parallel_steps,
    item_with_biggest_admissible_n_proc,
)


def test_group_items_by_parallel_steps():
    class item_mock:
        def __init__(self, name, n_proc):
            self.name = name
            self.n_proc = n_proc

    n_workers = 4
    items = [
        item_mock("a", 2),
        item_mock("b", 3),
        item_mock("c", 1),
        item_mock("d", 100),
        item_mock("e", 1),
        item_mock("f", 1),
    ]

    items_by_steps, items_to_skip = group_items_by_parallel_steps(items, n_workers)
    assert len(items_by_steps) == 2
    assert len(items_by_steps[0]) == 2
    assert len(items_by_steps[1]) == 3
    assert items_by_steps[0][0].name == "b"
    assert items_by_steps[0][1].name == "c"
    assert items_by_steps[1][0].name == "a"
    assert items_by_steps[1][1].name == "e"
    assert items_by_steps[1][2].name == "f"

    assert len(items_to_skip) == 1
    assert items_to_skip[0].name == "d"


def test_item_with_biggest_admissible_n_proc():
    class item_mock:
        def __init__(self, n_proc):
            self.n_proc = n_proc

    items = [
        item_mock(1),  # 0
        item_mock(1),  # 1
        item_mock(2),  # 2
        item_mock(4),  # 3
    ]

    # For the check `assert item_with_biggest_admissible_n_proc(items, 1) == 0`
    # 1 would have worked instead of 0, but we prefer the first one
    assert item_with_biggest_admissible_n_proc(items, 0) == -1
    assert item_with_biggest_admissible_n_proc(items, 1) == 0
    assert item_with_biggest_admissible_n_proc(items, 2) == 2
    assert item_with_biggest_admissible_n_proc(items, 3) == 2
    assert item_with_biggest_admissible_n_proc(items, 4) == 3
    assert item_with_biggest_admissible_n_proc(items, 5) == 3
