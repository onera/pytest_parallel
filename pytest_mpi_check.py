# -*- coding: utf-8 -*-

import pytest


def pytest_addoption(parser):
    group = parser.getgroup('mpi-check')
    group.addoption(
        '--foo',
        action='store',
        dest='dest_foo',
        default='2020',
        help='Set the value for the fixture "bar".'
    )

    parser.addini('HELLO', 'Dummy pytest.ini setting')


@pytest.fixture
def bar(request):
    return request.config.option.dest_foo

# --------------------------------------------------------------------------
@pytest.mark.tryfirst
def pytest_runtestloop(session):
  """
  """
  print("Mon super sous-modules")
