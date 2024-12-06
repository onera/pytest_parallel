"""
  Test that pytest_parallel gives the correct outputs
  by running it on a set of examples,
  then comparing it to template references
"""


# pytest_parallel MUST NOT be plugged in its testing framework environement
# it will be plugged by the framework when needed (see `run_pytest_parallel_test`)
# (else we would use pytest_parallel to test pytest_parallel, which is logically wrong)
import os
pytest_plugins = os.getenv('PYTEST_PLUGINS')
assert pytest_plugins is None or 'pytest_parallel.plugin' not in pytest_plugins

import sys
import re
import subprocess
from pathlib import Path
import pytest


root_dir = Path(__file__).parent
tests_dir = root_dir / "pytest_parallel_tests"
refs_dir = root_dir / "pytest_parallel_refs"
output_dir = root_dir / "pytest_parallel_output"
stderr_dir = output_dir / "stderr"
Path.mkdir(output_dir, exist_ok=True)
Path.mkdir(stderr_dir, exist_ok=True)


def ref_match(filename):
    template_path = refs_dir / filename
    with open(template_path, "r", encoding="utf-8") as f:
        ref_regex = f.read()
    output_path = output_dir / filename
    with open(output_path, "r", encoding="utf-8") as f:
        result = f.read()
    if not re.search(ref_regex, result, flags=re.DOTALL):
        print("ref: ", ref_regex)
        print("outfile: ", result)
    return re.search(ref_regex, result, flags=re.DOTALL)


def run_pytest_parallel_test(test_name, n_workers, scheduler, capfd, suffix=""):
    test_file_path = f"{tests_dir}/test_{test_name}.py"
    output_file_name = f"terminal_{test_name}{suffix}"
    output_file_path = output_dir / output_file_name
    stderr_file_path = stderr_dir / output_file_name

    # remove from eventual previous runs to be sure
    output_file_path.unlink(missing_ok=True)
    stderr_file_path.unlink(missing_ok=True)

    test_env = os.environ.copy()
    # To test pytest_parallel, we can need to launch pytest with it
    if "PYTEST_DISABLE_PLUGIN_AUTOLOAD" not in test_env:
        test_env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    cmd = f"mpiexec -n {n_workers} pytest -p pytest_parallel.plugin -s -ra -vv --color=no --scheduler={scheduler} {test_file_path}"
    #cmd = f"pytest -p pytest_parallel.plugin -s -ra -vv --color=no --scheduler={scheduler} --slurm_options='--time=00:30:00 --qos=co_short_std --ntasks={n_workers}' {test_file_path}"
    subprocess.run(cmd, shell=True, text=True, env=test_env)
    captured = capfd.readouterr()
    with open(output_file_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(captured.out)
    if not ref_match(output_file_name):
        print("err: ", captured.err)
        print("out: ", captured.out.replace(os.linesep, "\n"))
    assert ref_match(output_file_name)


param_scheduler = ["sequential", "static", "dynamic"]
# TODO "slurm" scheduler
#param_scheduler = ["slurm"]
if sys.platform == "win32":
  param_scheduler = ["sequential", "static"]

# fmt: off
@pytest.mark.parametrize("scheduler", param_scheduler)
class TestPytestParallel:
    def test_00(self, scheduler, capfd): run_pytest_parallel_test('seq'                             , 1, scheduler, capfd)

    def test_01(self, scheduler, capfd): run_pytest_parallel_test('two_success_tests_one_proc'      , 1, scheduler, capfd) # need at least 1 proc
    def test_02(self, scheduler, capfd): run_pytest_parallel_test('two_success_tests_one_proc'      , 2, scheduler, capfd) # 2 tests executing concurrently
    def test_04(self, scheduler, capfd): run_pytest_parallel_test('two_success_tests_one_proc'      , 4, scheduler, capfd) # 2 tests executing concurrently, 2 procs do nothing
  
    def test_05(self, scheduler, capfd): run_pytest_parallel_test('two_fail_tests_one_proc'         , 1, scheduler, capfd) # same but failing
    def test_06(self, scheduler, capfd): run_pytest_parallel_test('two_fail_tests_one_proc'         , 2, scheduler, capfd)
    def test_07(self, scheduler, capfd): run_pytest_parallel_test('two_fail_tests_one_proc'         , 4, scheduler, capfd)
  
    def test_08(self, scheduler, capfd): run_pytest_parallel_test('two_success_tests_two_procs'     , 2, scheduler, capfd) # need at least 2 procs
    def test_09(self, scheduler, capfd): run_pytest_parallel_test('two_success_tests_two_procs'     , 4, scheduler, capfd) # 4 tests (needing 2 procs each) executing concurrently
    def test_10(self, scheduler, capfd): run_pytest_parallel_test('two_success_tests_two_procs'     , 1, scheduler, capfd, suffix='_skip') # the two test will be skipped (not enough procs)
  
    def test_11(self, scheduler, capfd): run_pytest_parallel_test('two_fail_tests_two_procs'        , 2, scheduler, capfd) # same but failing
    def test_12(self, scheduler, capfd): run_pytest_parallel_test('two_fail_tests_two_procs'        , 4, scheduler, capfd)
    def test_13(self, scheduler, capfd): run_pytest_parallel_test('two_fail_tests_two_procs'        , 1, scheduler, capfd, suffix='_skip')
  
    def test_14(self, scheduler, capfd): run_pytest_parallel_test('success_0_fail_1'                , 2, scheduler, capfd) # one test failing (succeed one rank 0, fail on rank 1)
  
    def test_15(self, scheduler, capfd): run_pytest_parallel_test('two_success_fail_tests_two_procs', 2, scheduler, capfd) # one test succeeds, one test fails
    def test_16(self, scheduler, capfd): run_pytest_parallel_test('two_success_fail_tests_two_procs', 4, scheduler, capfd) # same, more procs
  
    def test_17(self, scheduler, capfd): run_pytest_parallel_test('fixture_error'                   , 1, scheduler, capfd) # check that fixture errors are correctly reported
  
    def test_18(self, scheduler, capfd): run_pytest_parallel_test('parametrize'                     , 2, scheduler, capfd) # check the parametrize API 
  
    def test_19(self, scheduler, capfd): run_pytest_parallel_test('scheduling'                      , 4, scheduler, capfd) # check 'real' case
    def test_20(self, scheduler, capfd): run_pytest_parallel_test('fail_complex_assert_two_procs'   , 2, scheduler, capfd) # check 'complex' error message
# fmt: on

## If one test fail, it may be useful to debug regex matching along the following lines
#test = 'two_fail_tests_one_proc'
#file = 'terminal_'+test
#
#template_path = refs_dir/file
#with open(template_path, 'r') as f:
#    ref_regex = f.read()
#output_path = output_dir/file
#with open(output_path, 'r') as f:
#    result = f.read()
#
#print(re.findall(ref_regex, result, flags=re.DOTALL))
