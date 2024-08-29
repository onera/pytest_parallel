import sys
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
