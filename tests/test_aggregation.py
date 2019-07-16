#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import unittest
import math

from mynbou.aggregation import *


class TestAggregations(unittest.TestCase):
    """Test aggregation methods."""

    def test_median(self):
        vals1 = sorted([0, 1, 5, 0, 0, 3, 2.1, 0.0009, 0.5])
        vals2 = sorted([0, 1, 5, 0, 0, 3, 2.1, 0.0009, 0.5, 0.3])

        self.assertEqual(vals1[4], median([0, 1, 5, 0, 0, 3, 2.1, 0.0009, 0.5]))
        self.assertEqual((vals2[4] + vals2[5]) / 2, median([0, 1, 5, 0, 0, 3, 2.1, 0.0009, 0.5, 0.3]))

    def test_stddev(self):
        vals = [2, 10]
        self.assertEqual(4, stddev(vals))

        vals = [0, 0]
        self.assertEqual(0, stddev(vals))

        vals = [0, math.nan]
        self.assertTrue(math.isnan(stddev(vals)))

    def test_cov(self):
        vals = [2, 10]
        self.assertEqual(0.6666666666666666, cov(vals))

        vals = [0, 0]
        self.assertEqual(0, cov(vals))

        vals = [0, math.nan]
        self.assertEqual(0, cov(vals))

    def test_gini(self):
        vals = [2, 10]
        self.assertEqual(-1.1666666666666665, gini(vals))

        vals = [0, 0]
        self.assertEqual(0, gini(vals))

        vals = [0, math.nan]
        self.assertTrue(math.isnan(gini(vals)))

    def test_hoover(self):
        vals = [0, 0]
        self.assertEqual(0, hoover(vals))

        vals = [0, math.nan]
        self.assertEqual(0, hoover(vals))

        vals = [2, 10]
        self.assertEqual(0.33333333333333337, hoover(vals))

    def test_atkinson(self):
        vals = [2, 10]
        self.assertEqual(0.12732200375003488, atkinson(vals))

        vals = [0, 0]
        self.assertEqual(0, atkinson(vals))

        vals = [0, math.nan]
        self.assertTrue(math.isnan(atkinson(vals)))

    def test_shannon(self):
        vals = [2, 10]
        self.assertEqual(0.34657359027997264, shannon_entropy(vals))

        vals = [0, 0]
        self.assertEqual(0, shannon_entropy(vals))

        vals = [0, math.nan]
        self.assertTrue(math.isnan(shannon_entropy(vals)))

    def test_generalized_entropy(self):
        vals = [2, 10]
        self.assertEqual(0.26331056414913734, generalized_entropy(vals))

        vals = [0, 0]
        self.assertEqual(0, generalized_entropy(vals))

        vals = [0, math.nan]
        self.assertEqual(0, generalized_entropy(vals))

    def test_theil_index(self):
        vals = [2, 10]
        self.assertEqual(0.24258597169364066, theil(vals))

        vals = [0, 0]
        self.assertEqual(0, theil(vals))

        vals = [0, math.nan]
        self.assertEqual(0, theil(vals))