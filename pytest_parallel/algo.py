"""
  These algorithms are similar to those of the STL
"""
import operator


def identity(elem):
    return elem


def partition(xs, pred):
    """
    partitions sequence `xs` into
      `xs_true`  with elements of `xs` that       satisfy predicate `pred`
      `xs_false` with elements of `xs` that don't satisfy predicate `pred`
    then returns `xs_true`, `xs_false`

    Complexity:
      with N = len(xs)
      Time:
        N applications of `pred`.
        N calls to list.append
      Space
        N elements
    """
    xs_true = []
    xs_false = []
    for elem in xs:
        if pred(elem):
            xs_true.append(elem)
        else:
            xs_false.append(elem)
    return xs_true, xs_false


def partition_point(xs, pred):
    """
    Gives the partition point of sequence `xs`
    That is, the index i where
          prod(xs[k]) for all k < i
      not prod(xs[k]) for all k >= i

    Precondition: `xs` is supposed to be partitioned into
      first elements for which `pred` is false
      then elements for which `pred` is true

    Complexity:
      with N = len(xs)
      Time:
        log_2(N) applications of `pred`.
      Space
        Constant
    """
    i = 0
    j = len(xs)
    while i < j:
        mid = (i + j) // 2
        if pred(xs[mid]):
            i = mid + 1
        else:
            j = mid
    return i


def lower_bound(xs, value, key=identity, comp=operator.lt):
    def pred(elem):
        return comp(key(elem), value)

    return partition_point(xs, pred)


def upper_bound(xs, value, key=identity, comp=operator.lt):
    def pred(elem):
        return not comp(value, key(elem))

    return partition_point(xs, pred)
