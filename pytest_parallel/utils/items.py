import pytest
from _pytest.nodes import Item


def get_n_proc_for_test(item: Item) -> int :
    if not hasattr(item, 'callspec'): return 1 # no callspec, so no `comm` => sequential test case
    try:
        return item.callspec.getparam('comm')
    except ValueError: # no `comm` => sequential test case
        return 1


def add_n_procs(items):
    for item in items:
        item.n_proc = get_n_proc_for_test(item)


def run_item_test(item, nextitem, session):
    item.config.hook.pytest_runtest_protocol(item=item, nextitem=nextitem)
    if session.shouldfail:
        raise session.Failed(session.shouldfail)
    if session.shouldstop:
        raise session.Interrupted(session.shouldstop)


def mark_original_index(items):
    for i, item in enumerate(items):
        item.original_index = i


def mark_skip(item, ntasks):
    n_proc_test = get_n_proc_for_test(item)
    skip_msg = f"Not enough procs to execute: {n_proc_test} required but only {ntasks} available"
    item.add_marker(pytest.mark.skip(reason=skip_msg), append=False)
    item.marker_mpi_skip = True
