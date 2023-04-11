"""
  Test that pytest_parallel gives the correct outputs
  by running it on a set of examples,
  then comparing it to template references

  We run the checks with pytest
  But, since we are in the process of testing pytest_parallel,
  the testing framework (this file!) MUST DISABLE pytest_parallel when we run its tests
  (but of course its tests will in turn run tests with pytest_parallel enabled)
"""
import os
assert 'pytest_parallel.plugin' not in os.getenv('PYTEST_PLUGINS') # pytest_parallel MUST NOT be plugged in its testing framework environement
                                                                   # it will be plugged in by the framework when needed

import re
import pytest
from pathlib import Path
import subprocess

root_dir = Path(__file__).parent
tests_dir  = root_dir/'pytest_parallel_tests'
refs_dir   = root_dir/'pytest_parallel_refs'
output_dir = root_dir/'pytest_parallel_output'
stderr_dir = output_dir/'stderr'
Path.mkdir(output_dir,exist_ok=True)
Path.mkdir(stderr_dir,exist_ok=True)

def ref_match(file):
  template_path = refs_dir/file
  with open(template_path, 'r') as f:
    ref_regex = f.read()
  output_path = output_dir/file
  with open(output_path, 'r') as f:
    result = f.read()

  return re.fullmatch(ref_regex, result, flags=re.DOTALL)

def run_pytest_parallel_test(test_name, n_workers, scheduler, suffix=''):
  assert 'pytest_parallel.plugin' not in os.getenv('PYTEST_PLUGINS') # pytest_parallel MUST NOT be plugged in its testing framework environement

  test_file_path = f'{tests_dir}/test_{test_name}.py'
  output_file_name = f'terminal_{test_name}{suffix}'
  output_file_path = output_dir/output_file_name
  stderr_file_path = stderr_dir/output_file_name

  # remove from eventual previous runs to be sure
  output_file_path.unlink(missing_ok=True)
  stderr_file_path.unlink(missing_ok=True)

  print(output_file_path)
  cmd  = f'export PYTEST_PLUGINS=pytest_parallel.plugin\n' # re-enable the plugin when we execute the command
  #cmd += f'mpirun -np {n_workers} pytest -s -ra -vv --color=no --scheduler={scheduler} {test_file_path}'
  cmd += f'mpirun -np {n_workers} pytest -s -ra -vv --color=no --scheduler={scheduler} {test_file_path}'
  cmd += f' > {output_file_path}  2> {stderr_file_path}' # redirections. stderr is actually not very useful (since the tests errors are reported in stdout by PyTest)
  subprocess.run(cmd, shell=True)
  assert ref_match(output_file_name)


#@pytest.mark.parametrize('scheduler',['sequential','static'])
@pytest.mark.parametrize('scheduler',['dynamic'])
class TestPytestParallel:
  def test_00(self, scheduler): run_pytest_parallel_test('seq'                             , 1, scheduler)
  
  #def test_01(self, scheduler): run_pytest_parallel_test('two_success_tests_one_proc'      , 1, scheduler) # need at least 1 proc
  #def test_02(self, scheduler): run_pytest_parallel_test('two_success_tests_one_proc'      , 2, scheduler) # 2 tests executing concurrently
  #def test_04(self, scheduler): run_pytest_parallel_test('two_success_tests_one_proc'      , 4, scheduler) # 2 tests executing concurrently, 2 procs do nothing

  #def test_05(self, scheduler): run_pytest_parallel_test('two_fail_tests_one_proc'         , 1, scheduler) # same but failing
  #def test_06(self, scheduler): run_pytest_parallel_test('two_fail_tests_one_proc'         , 2, scheduler)
  #def test_07(self, scheduler): run_pytest_parallel_test('two_fail_tests_one_proc'         , 4, scheduler)

  #def test_08(self, scheduler): run_pytest_parallel_test('two_success_tests_two_procs'     , 2, scheduler) # need at least 2 procs
  #def test_09(self, scheduler): run_pytest_parallel_test('two_success_tests_two_procs'     , 4, scheduler) # 4 tests (needing 2 procs each) executing concurrently
  #def test_10(self, scheduler): run_pytest_parallel_test('two_success_tests_two_procs'     , 1, scheduler, suffix='_skip') # the two test will be skipped (not enough procs)

  #def test_11(self, scheduler): run_pytest_parallel_test('two_fail_tests_two_procs'        , 2, scheduler) # same but failing
  #def test_12(self, scheduler): run_pytest_parallel_test('two_fail_tests_two_procs'        , 4, scheduler)
  #def test_13(self, scheduler): run_pytest_parallel_test('two_fail_tests_two_procs'        , 1, scheduler, suffix='_skip')

  #def test_14(self, scheduler): run_pytest_parallel_test('success_0_fail_1'                , 2, scheduler) # one test failing (succeed one rank 0, fail on rank 1)

  #def test_15(self, scheduler): run_pytest_parallel_test('two_success_fail_tests_two_procs', 2, scheduler) # one test succeeds, one test fails
  #def test_16(self, scheduler): run_pytest_parallel_test('two_success_fail_tests_two_procs', 4, scheduler) # same, more procs

  #def test_17(self, scheduler): run_pytest_parallel_test('fixture_error'                   , 1, scheduler) # check that fixture errors are correctly reported

  #def test_18(self, scheduler): run_pytest_parallel_test('parametrize'                     , 2, scheduler) # check the parametrize API 


#def test_18(): run_pytest_parallel_test('scheduling' , 4, 'static')
#def test_19(): run_pytest_parallel_test('scheduling' , 4, 'dynamic')



test = 'parametrize'
file = 'terminal_'+test

#refs_dir = Path('/scratchm/bberthou/projects/fs_cgns_adapter/external/pytest-mpi-check/test/pytest_parallel_refs')
#output_dir = Path('/scratchm/bberthou/projects/fs_cgns_adapter/external/pytest-mpi-check/test/pytest_parallel_refs')
template_path = refs_dir/file
with open(template_path, 'r') as f:
  ref_regex = f.read()
output_path = output_dir/file
with open(output_path, 'r') as f:
  result = f.read()

print(re.findall(ref_regex, result, flags=re.DOTALL))
