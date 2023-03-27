import pytest

@pytest.fixture
def tutu():
  titi # <--- ERROR HERE
  return 0

def test_toto1(tutu):
  assert tutu==0
