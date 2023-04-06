

echo "============== Test 1 =============="
mpirun -np 1 pytest -s -ra -vv /scratchm/bberthou/projects/fs_cgns_adapter/external/pytest-mpi-check/tests/test_.py > test1.log
echo "============== Diff 1 =============="
diff test1.log ref/test1.log 
echo "\n\n\n\n"

echo "============== Test 2 =============="
mpirun -np 1 pytest -s -ra -vv /scratchm/bberthou/projects/fs_cgns_adapter/external/pytest-mpi-check/tests/test_1.py > test2.log
echo "============== Diff 2 =============="
diff test2.log ref/test2.log 
echo "\n\n\n\n"

echo "============== Test 3 =============="
mpirun -np 2 pytest -s -ra -vv /scratchm/bberthou/projects/fs_cgns_adapter/external/pytest-mpi-check/tests/test_1.py > test3.log
echo "============== Diff 3 =============="
diff test3.log ref/test3.log 
echo "\n\n\n\n"

echo "============== Test 4 =============="
pytest -s -ra -vv /scratchm/bberthou/projects/fs_cgns_adapter/external/pytest-mpi-check/tests/test_fixture_error.py > test4.log
echo "============== Diff 4 =============="
diff test4.log ref/test4.log 



mpirun -np 1 pytest -s -ra -vv /scratchm/bberthou/projects/fs_cgns_adapter/external/pytest-mpi-check/tests/test_two_failing_tests.py
mpirun -np 2 pytest -s -ra -vv /scratchm/bberthou/projects/fs_cgns_adapter/external/pytest-mpi-check/tests/test_two_failing_tests.py


# seq, static
mpirun -np 1 pytest -s -ra -vv test_two_fail_tests_one_proc.py
mpirun -np 2 pytest -s -ra -vv test_two_fail_tests_two_proc.py
mpirun -np 2 pytest -s -ra -vv test_two_success_fail_tests_two_procs.py
mpirun -np 2 pytest -s -ra -vv test_two_success_tests_two_proc.py

mpirun -np 2 pytest -s -ra -vv test_two_fail_tests_one_proc.py
mpirun -np 4 pytest -s -ra -vv test_two_fail_tests_two_proc.py
mpirun -np 4 pytest -s -ra -vv test_two_success_fail_tests_two_procs.py
mpirun -np 4 pytest -s -ra -vv test_two_success_tests_two_proc.py
