def group_items_by_parallel_steps(items, n_workers):
    _items = sorted(items, key=lambda item: item.n_proc, reverse=True)

    remaining_n_procs_by_step = []
    items_by_step = []
    items_to_skip = []
    for item in _items:
        if item.n_proc > n_workers:
            items_to_skip += [item]
        else:
            found_step = False
            for idx, remaining_procs in enumerate(remaining_n_procs_by_step):
                if item.n_proc <= remaining_procs:
                    items_by_step[idx] += [item]
                    remaining_n_procs_by_step[idx] -= item.n_proc
                    found_step = True
                    break
            if not found_step:
                items_by_step += [[item]]
                remaining_n_procs_by_step += [n_workers - item.n_proc]

    return items_by_step, items_to_skip


