
# --------------------------------------------------------------------------
# @pytest.fixture
# def sub_comm(request):
#   """
#   Method for create the sub communicator associate with a test
#   This method cannot work if the scheduler is a priori
#   """
#   # return request._pyfuncitem._sub_comm
#   print("Create sub_comm for each test ")
#   comm = MPI.COMM_WORLD

#   n_proc = request.param

#   # Groups communicator creation
#   gprocs   = [i for i in range(n_proc)]
#   group    = comm.Get_group()
#   subgroup = group.Incl(gprocs)
#   subcomm  = comm.Create(subgroup)

#   # comm.Barrier()

#   return subcomm

# @pytest.mark.tryfirst
# def pytest_unconfigure(config):
#   print("*"*100)
#   print(dir(html))
#   print("*"*100)
#   print(html.reports)
#   for nodeid, res in html.reports.items():
#     print("res::", dir(res))

#   print("x"*100)
#   for test_name, test_reports in html.reports.items():
#     print("pytest_unconfigure ----> ", test_name, len(test_reports))
#     Un truc bizarre se passe dans pytest_html, qui "refait" les rapports, donc on passe 2 fois ici
#     for test_report in test_reports:
#       print("           ----> ", test_report.when, test_report.outcome, test_report.longrepr)
#       print("\n"+"o"*100)
#   print("x"*100)

#   > Tentative finalize :
#   for test_name, test_reports in html.reports.items():
#     for test_report in test_reports:
#       if( test_report.longrepr and isinstance(test_report.longrepr, ExceptionChainRepr)):
#         print("xoxo"*10)
#         test_report.longrepr.addsection( "titi", "oooooo")
#         test_report.longrepr.addsection( "toto", "iiiiii")



# @pytest.mark.tryfirst
# def pytest_terminal_summary(terminalreporter):
#     print("*******"*100)

# @pytest.mark.tryfirst
# def pytest_report_teststatus(report):
#     print("pytest_report_teststatus::", report.nodeid, report.when)


# @pytest.mark.tryfirst
# def pytest_sessionfinish(session):
#   html = getattr(session, "_html", None)
#   for i, item in enumerate(session.items):
#     # print("\n ****** "*10, dir(item))
#     item.add_report_section("call", "titi", "ooo")

# --------------------------------------------------------------------------
# @pytest.mark.tryfirst
# def pytest_runtest_logreport(report):
#   # print("MPI:: pytest_runtest_logreport", report.when)
#   # print("MPI:: pytest_runtest_logreport oooooo ", report.longrepr)

#   # Chaque rang doit faire un rapport !
#   # Attention si le rang 0 n'a pas d'erreur il faut également créer l'objet


#   # print("x"*100, type(report), dir(report))
#   # if report.longrepr and isinstance(report.longrepr, ExceptionChainRepr):
#   #   print("oooooo", report.when, type(report.longrepr), dir(report.longrepr))
#   #   print(report.longrepr)
#   #   report.longrepr.addsection( "titi", "oooooo")
#   #   report.longrepr.addsection( "toto", "iiiiii")
#   # print("x"*100)
#     # report.longrepr += report.longrepr
#     # report.longrepr += report.longrepr
#   # print("MPI:: pytest_runtest_logreport", type(report.longrepr))
#   # print("MPI:: pytest_runtest_logreport", dir(report.longrepr))

#   # > Pour hook
#   # content_out = report.capstdout
#   # content_log = report.caplog
#   # content_err = report.capstderr

#   pass

# --------------------------------------------------------------------------
# @pytest.mark.tryfirst
# def pytest_collectreport(report):
#   print("MPI:: pytest_collectreport", report.when)
#   # if report.failed:
#   #   self.append_failed(report)


# A GARDER POUR LES SORTIES
# # if(comm.rank == i):
#   print("\n***************************", item.nodeid)
#   # print("***************************", item._sub_comm)
#   # print(i, item, dir(item), item.name, item.originalname)
#   # print("launch on {0} item : {1}".format(comm.rank, item))
#   # print(i, item)

#   # temp_ouput_file = 'maia_'
#   # sys.stdout = open(f"{temp_ouput_file(item.name)}_{MPI.COMM_WORLD.Get_rank()}", "w")
#   # sys.stdout = open(f"maia_{item.name}_{MPI.COMM_WORLD.Get_rank()}", "w")
#   # item.toto = i
#   # Create sub_comm !

# --------------------------------------------------------------------------
# @pytest.fixture
# def make_sub_comm(request):
#   """
#   """
#   comm = MPI.COMM_WORLD

#   # print(" request:: ", dir(request._pyfuncitem))
#   # print(" toto:: ", comm.rank, request._pyfuncitem.toto)
#   n_proc = request.param

#   # if(request._pyfuncitem.toto == comm.rank):
#   #   pytest.skip()
#   #   return None

#   return None

#   if(n_proc > comm.size):
#     pytest.skip()
#     return None

#   # Groups communicator creation
#   gprocs   = [i for i in range(n_proc)]
#   group    = comm.Get_group()
#   subgroup = group.Incl(gprocs)
#   # print(dir(comm))
#   # subcomm  = comm.Create(subgroup)      # Lock here - Collection among all procs
#   subcomm  = comm.Create_group(subgroup)  # Ok - Only collective amont groups

#   if(subcomm == MPI.COMM_NULL):
#     pytest.skip()

#   return subcomm

# def get_n_proc_for_test(item: Item) -> int :
#   # OOODLLLLDDDD
#   # exit(2)
#   # print("dir(item)::", dir(item.keywords))
#   # for mark in item.iter_markers(name="mpi_test"):
#   #   if mark.args:
#   #     raise ValueError("mpi mark does not take positional args")
#   #   n_proc_test = mark.kwargs.get('comm_size')

#   #   # print("**** item:: ", dir(item))
#   #   # print("**** request:: ", dir(item._pyfuncitem))
#   #   # print("**** request:: ", dir(item._pyfuncitem.funcargnames))
#   #   # print("**** request:: ", item._pyfuncitem.funcargnames)
#   #   # print("**** request:: ", item._pyfuncitem.funcargs)
#   #   # print("mark.kwargs::", mark.kwargs)
#   #   if(n_proc_test is None):
#   #     raise ValueError("We need to specify a comm_size for the test")
#   # return n_proc_test
