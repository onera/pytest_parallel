# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import pytest


@pytest.fixture
def comm(request):
    """
    Only return a previous MPI Communicator (build at prepare step )
    """
    return request._pyfuncitem._sub_comm  # TODO clean


## TODO backward compatibility begin
@pytest.fixture
def sub_comm(request):
    return request._pyfuncitem._sub_comm
