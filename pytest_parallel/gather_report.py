from mpi4py import MPI
from _pytest._code.code import (
    ExceptionChainRepr,
    ReprTraceback,
    ReprEntryNative,
    ReprFileLocation,
)


def gather_report(mpi_reports, n_sub_rank):
    assert len(mpi_reports) == n_sub_rank

    report_init = mpi_reports[0]
    goutcome = report_init.outcome
    glongrepr = report_init.longrepr

    collect_longrepr = []
    # > We need to rebuild a TestReport object, location can be false # TODO ?
    for i_sub_rank, test_report in enumerate(mpi_reports):
        if test_report.outcome == "failed":
            goutcome = "failed"

        if test_report.longrepr:
            msg = f"On rank {i_sub_rank} of {n_sub_rank}"
            full_msg = f"\n-------------------------------- {msg} --------------------------------"
            fake_trace_back = ReprTraceback([ReprEntryNative(full_msg)], None, None)
            collect_longrepr.append(
                (fake_trace_back, ReprFileLocation(*report_init.location), None)
            )
            collect_longrepr.append(
                (test_report.longrepr, ReprFileLocation(*report_init.location), None)
            )

    if len(collect_longrepr) > 0:
        glongrepr = ExceptionChainRepr(collect_longrepr)

    return goutcome, glongrepr


def gather_report_on_local_rank_0(report):
    """
    Gather reports from all procs participating in the test on rank 0 of the sub_comm
    """
    sub_comm = report.sub_comm
    del report.sub_comm  # No need to keep it in the report
    # Furthermore we need to serialize the report
    # and mpi4py does not know how to serialize report.sub_comm
    i_sub_rank = sub_comm.Get_rank()
    n_sub_rank = sub_comm.Get_size()

    if (
        report.outcome != "skipped"
    ):  # Skipped test are only known by proc 0 -> no merge required
        # Warning: PyTest reports can actually be quite big
        request = sub_comm.isend(report, dest=0, tag=i_sub_rank)

        if i_sub_rank == 0:
            mpi_reports = n_sub_rank * [None]
            for _ in range(n_sub_rank):
                status = MPI.Status()

                mpi_report = sub_comm.recv(
                    source=MPI.ANY_SOURCE, tag=MPI.ANY_TAG, status=status
                )
                mpi_reports[status.Get_source()] = mpi_report

            assert (
                None not in mpi_reports
            )  # should have received from all ranks of `sub_comm`
            goutcome, glongrepr = gather_report(mpi_reports, n_sub_rank)

            report.outcome = goutcome
            report.longrepr = glongrepr

        request.wait()

    sub_comm.barrier()
