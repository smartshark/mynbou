#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This module contains functions for calculation of aggregations for lists of values.

The calculations here are verbatim taken from Zhang et al. :cite:`zhang`.
"""


import math
import statistics
from fractions import Fraction


def msum(iterable):
    """Full precision summation using multiple floats for intermediate values.

    Rounded x+y stored in hi with the round-off stored in lo.  Together
    hi+lo are exactly equal to x+y.  The inner loop applies hi/lo summation
    to each partial so that the list of partial sums remains exact.
    Depends on IEEE-754 arithmetic guarantees.  See proof of correctness
    `here <http://www-2.cs.cmu.edu/afs/cs/project/quake/public/papers/robust-arithmetic.ps>`_

    `recipe source <http://code.activestate.com/recipes/393090/>`_
    """
    partials = []  # sorted, non-overlapping partial sums
    for x in iterable:
        i = 0
        for y in partials:
            if abs(x) < abs(y):
                x, y = y, x
            hi = x + y
            lo = y - (hi - x)
            if lo:
                partials[i] = lo
                i += 1
            x = hi
        partials[i:] = [x]
    return sum(partials, 0.0)


def median(values):
    values = sorted(values)
    if len(values) % 2 == 0:
        return 0.5 * (values[math.floor(len(values) / 2)] + values[math.floor((len(values) - 1) / 2)])
    else:
        return values[math.floor((len(values)) / 2)]


def stddev(values):
    values = sorted(values)
    N = len(values)

    m = statistics.mean(values)
    n = [math.pow(v - m, 2) for v in values]

    return math.sqrt(sum(n) / N)


def cov(values):
    values = sorted(values)
    mean = statistics.mean(values)
    ret = 0
    if mean > 0:
        ret = stddev(values) / mean
    return ret


def gini(values):
    if len(values) * sum(values) == 0:
        return 0
    values = sorted(values)
    first = 2 / (len(values) * sum(values))

    second = []
    for i, v in enumerate(values):
        second.append(v * (i + 1))  # +1 because enumerate starts from 0 and the formula starts from 1
    second = sum(second) - (len(values) + 1) * sum(values)

    return first * second


def hoover(values):
    values = sorted(values)

    if sum(values) == 0 or math.isnan(sum(values)):
        return 0

    s = [abs(Fraction(v, sum(values)) - Fraction(1, len(values))) for v in values]  # seems more exact than passing the div
    return 0.5 * sum(s)


def atkinson(values):
    values = sorted(values)
    mean = statistics.mean(values)

    if mean == 0:
        return 0

    inner = []
    for value in values:
        if value > 0:
            inner.append(math.sqrt(value))
    inner = msum(inner) / len(values)
    s = math.pow(inner, 2)
    return 1 - (s / mean)


def shannon_entropy(values):
    values = sorted(values)
    N = len(values)

    freq = {}
    for value in values:
        if math.isnan(value):
            return math.nan
        if value not in freq.keys():
            freq[value] = 0
        freq[value] += 1

    res = []
    for value in values:
        fn = Fraction(freq[value], N)
        lfn = math.log(Fraction(freq[value], N))

        res.append(fn * lfn)

    return -(1 / N) * msum(res)


def generalized_entropy(values):
    alpha = 0.5
    values = sorted(values)
    N = len(values)
    mean = statistics.mean(values)

    if mean == 0:
        return 0

    prefix = (-1 / (N * alpha * (1 - alpha)))
    res = []
    for value in values:
        if math.isnan(value) or math.isnan(mean):
            continue
        elif int(value) == value and math.floor(mean) > 0:
            try:
                vm = Fraction(int(value), math.floor(mean))
                res.append(math.pow(vm, alpha) - 1)
            except TypeError:
                print(type(value), value)
                print(type(math.floor(mean)), math.floor(mean))
        else:
            vm = value / mean
            if vm > 0:
                res.append(math.pow(vm, alpha) - 1)

    return prefix * msum(res)


def theil(values):
    values = sorted(values)
    N = len(values)
    mean = statistics.mean(values)

    res = []
    for value in values:
        vm = 0
        if math.isnan(value) or math.isnan(mean):
            continue
        elif int(value) == value and math.floor(mean) > 0:
            vm = Fraction(int(value), math.floor(mean))
        elif mean > 0:
            vm = value / mean
        if vm > 0:
            res.append(vm * math.log(vm))
    return msum(res) / N
