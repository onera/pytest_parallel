import pytest

@pytest.fixture
def my_fixture():
  unknown_token # <--- ERROR HERE
  return 0

def test_fixture_error(my_fixture):
  assert my_fixture==0
