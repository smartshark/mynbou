#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import math

import datetime

from mynbou.metrics.change import hassan, dambros, moser

INSTANCES = {'test.py': {'age': 16,
                         'ages': [0, 2, 4, 4, 16],
                         'aliases': [],
                         'authors': ['Test User (test@test.local)',
                                     'Test User (test@test.local)',
                                     'Test User (test@test.local)',
                                     'Test User (test@test.local)',
                                     'Test User (test@test.local)'],
                         'bug_fixes': ['BUG-123'],
                         'change_types': [],
                         'changesets': [2, 1, 1, 1, 3],
                         'commit_messages': ['added test.py and test2.py\n',
                                             'modified test.py\n',
                                             'remove a() in test.py\n',
                                             'add d() in test.py\n',
                                             'add c() in test.py, add d() in test2.py, '
                                             'include test3.py\n'],
                         'days_from_release': [16, 14, 12, 11, 0],
                         'first_occurence': datetime.datetime(2018, 1, 1, 3, 1, 1, tzinfo=datetime.timezone(datetime.timedelta(seconds=7200))),
                         'lines_added': [3, 3, 0, 2, 3],
                         'lines_deleted': [0, 0, 3, 0, 0],
                         'linked_issues': [],
                         'refactorings': [],
                         'revisions': ['e15c0198ebf15201b969c7798c77d3b52f9bbe34',
                                       '33af2ad3f137641842e819d32c7f3906c4481086',
                                       '4f9d7698470044d7f1e788e0c0089f1d0d0893e9',
                                       '49dfd33554f3bb8ffa20f2253d2425295b8b1abd',
                                       'a97319f6338d4c6e72f42a313ba9d8290c8b7758']},
             'test2.py': {'age': 16,
                          'ages': [0, 8, 16],
                          'aliases': [],
                          'authors': ['Test User (test@test.local)',
                                      'Test User (test@test.local)',
                                      'Test User (test@test.local)'],
                          'bug_fixes': ['BUG-123'],
                          'change_types': [],
                          'changesets': [2, 1, 3],
                          'commit_messages': ['added test.py and test2.py\n',
                                              'add b() in test2.py\n',
                                              'add c() in test.py, add d() in test2.py, '
                                              'include test3.py\n'],
                          'days_from_release': [16, 8, 0],
                          'first_occurence': datetime.datetime(2018, 1, 1, 3, 1, 1, tzinfo=datetime.timezone(datetime.timedelta(seconds=7200))),
                          'lines_added': [3, 3, 3],
                          'lines_deleted': [0, 0, 0],
                          'linked_issues': [],
                          'refactorings': [],
                          'revisions': ['e15c0198ebf15201b969c7798c77d3b52f9bbe34',
                                        'edb3326db72ac0873b745f59048ba7a29c5ec87a',
                                        'a97319f6338d4c6e72f42a313ba9d8290c8b7758']},
             'test3.py': {'age': 0,
                          'ages': [0],
                          'aliases': [],
                          'authors': ['Test User (test@test.local)'],
                          'bug_fixes': [],
                          'change_types': [],
                          'changesets': [3],
                          'commit_messages': ['add c() in test.py, add d() in test2.py, '
                                              'include test3.py\n'],
                          'days_from_release': [0],
                          'first_occurence': datetime.datetime(2018, 1, 17, 3, 1, 1, tzinfo=datetime.timezone(datetime.timedelta(seconds=7200))),
                          'lines_added': [4],
                          'lines_deleted': [0],
                          'linked_issues': [],
                          'refactorings': [],
                          'revisions': ['a97319f6338d4c6e72f42a313ba9d8290c8b7758']}}


class TestChangeMetrics(unittest.TestCase):
    """Test Moser and Hassan change metrics."""

    def test_moser_metrics(self):
        """Happy path check for weighted age on our fixture."""
        moser_got = moser(INSTANCES)

        # weighted age formula: foreach change sum: (age * lines_added) / sum lines_added
        moser_wanted = {'test.py': {'MOSER_weighted_age': (0 * 3 + 2 * 3 + 4 * 0 + 4 * 2 + 16 * 3) / 11,
                                    'MOSER_authors': 1},
                        'test2.py': {'MOSER_weighted_age': (0 * 3 + 8 * 3 + 16 * 3) / 9,
                                     'MOSER_authors': 1},
                        'test3.py': {'MOSER_weighted_age': (0 * 4) / 4,
                                     'MOSER_authors': 1},
                        }

        # we only want to check for certain things
        check_wanted = ['MOSER_authors', 'MOSER_weighted_age']
        moser_test = {}
        for k, v in moser_got.items():
            moser_test[k] = {}
            for k2, v2 in v.items():
                if k2 in check_wanted:
                    moser_test[k][k2] = v2

        self.assertEqual(moser_test, moser_wanted)

    def test_hassan_metrics(self):
        """Happy path check for all hassan metrics on our fixture."""
        phi1 = 1
        phi2 = 1
        phi3 = 1

        have = hassan(INSTANCES, window_size_days=7, phi1=phi1, phi2=phi2, phi3=phi3)

        # formula for adaptive sizing entropy
        h1 = -((5 / 8) * math.log(5 / 8, 3) + (3 / 8) * math.log(3 / 8, 3))
        h2 = -((3 / 10) * math.log(3 / 10, 3) + (3 / 10) * math.log(3 / 10, 3) + (4 / 10) * math.log(4 / 10, 3))

        wanted = {'test.py': {'HASSAN_ldhcm': h1 / (phi2 * (2 + 1 - 1)) + h2 / (phi2 * (2 + 1 - 2)),
                              'HASSAN_lgdhcm': h1 / (phi3 * math.log(2 + 1.01 - 1)) + h2 / (phi3 * math.log(2 + 1.01 - 2)),
                              'HASSAN_edhcm': h1 / math.exp(phi1 * (2 - 1)) + h2 / math.exp(phi1 * (2 - 2)),
                              'HASSAN_whcm': (5 / 8) * h1 + (3 / 10) * h2,
                              'HASSAN_hcm': h1 + h2},
                  'test2.py': {'HASSAN_ldhcm': h1 / (phi2 * (2 + 1 - 1)) + h2 / (phi2 * (2 + 1 - 2)),
                               'HASSAN_lgdhcm': h1 / (phi3 * math.log(2 + 1.01 - 1)) + h2 / (phi3 * math.log(2 + 1.01 - 2)),
                               'HASSAN_edhcm': h1 / math.exp(phi1 * (2 - 1)) + h2 / math.exp(phi1 * (2 - 2)),
                               'HASSAN_whcm': (3 / 8) * h1 + (3 / 10) * h2,
                               'HASSAN_hcm': h1 + h2},
                  'test3.py': {'HASSAN_ldhcm': h2 / (phi2 * (1 + 1 - 1)),
                               'HASSAN_lgdhcm': h2 / (phi3 * math.log(1 + 1.01 - 1)),
                               'HASSAN_edhcm': h2 / math.exp(phi1 * (1 - 1)),
                               'HASSAN_whcm': (4 / 10) * h2,
                               'HASSAN_hcm': h2}}

        self.maxDiff = None
        self.assertEqual(have, wanted)

    def test_dambros(self):
        """Happy path check for all dambros metrics, here we do not use the fixture but define a delta matrix for two files, two timestepas and two metrics."""
        phi1 = 1
        phi2 = 1
        phi3 = 1
        alpha = 0.01

        # this is the example from D'Ambros et al. for one metric and two fiels in two columns (time steps)
        col1_metrica = -((40 / 50) * math.log(40 / 50, 2) + (10 / 50) * math.log(10 / 50, 2))
        col2_metrica = -((10 / 15) * math.log(10 / 15, 2) + (5 / 15) * math.log(5 / 15, 2))

        # this is another metric with negative deltas from which absolute values should be taken
        col1_metricb = -((5 / 15) * math.log(5 / 15, 2) + (10 / 15) * math.log(10 / 15, 2))
        col2_metricb = -((7 / 9) * math.log(7 / 9, 2) + (2 / 9) * math.log(2 / 9, 2))

        deltas2 = {'MetricA': {'FileA': [40, 10],
                               'FileB': [10, 5]},
                   'MetricB': {'FileA': [5, 7],
                               'FileB': [10, 2]}}

        have = dambros(deltas2['MetricA'], deltas2, alpha, phi1, phi2, phi3)

        edpchu_a_a = (1 + alpha * 40) / math.exp(phi1 * (2 - 1)) + (1 + alpha * 10) / math.exp(phi1 * (2 - 2))
        edpchu_a_b = (1 + alpha * 5) / math.exp(phi1 * (2 - 1)) + (1 + alpha * 7) / math.exp(phi1 * (2 - 2))
        edpchu_b_a = (1 + alpha * 10) / math.exp(phi1 * (2 - 1)) + (1 + alpha * 5) / math.exp(phi1 * (2 - 2))
        edpchu_b_b = (1 + alpha * 10) / math.exp(phi1 * (2 - 1)) + (1 + alpha * 2) / math.exp(phi1 * (2 - 2))

        ldpchu_a_a = (1 + alpha * 40) / (phi2 * (2 + 1 - 1)) + (1 + alpha * 10) / (phi2 * (2 + 1 - 2))
        ldpchu_a_b = (1 + alpha * 5) / (phi2 * (2 + 1 - 1)) + (1 + alpha * 7) / (phi2 * (2 + 1 - 2))
        ldpchu_b_a = (1 + alpha * 10) / (phi2 * (2 + 1 - 1)) + (1 + alpha * 5) / (phi2 * (2 + 1 - 2))
        ldpchu_b_b = (1 + alpha * 10) / (phi2 * (2 + 1 - 1)) + (1 + alpha * 2) / (phi2 * (2 + 1 - 2))

        lgdpchu_a_a = (1 + alpha * 40) / (phi3 * math.log(2 + 1.01 - 1)) + (1 + alpha * 10) / (phi3 * math.log(2 + 1.01 - 2))
        lgdpchu_a_b = (1 + alpha * 5) / (phi3 * math.log(2 + 1.01 - 1)) + (1 + alpha * 7) / (phi3 * math.log(2 + 1.01 - 2))
        lgdpchu_b_a = (1 + alpha * 10) / (phi3 * math.log(2 + 1.01 - 1)) + (1 + alpha * 5) / (phi3 * math.log(2 + 1.01 - 2))
        lgdpchu_b_b = (1 + alpha * 10) / (phi3 * math.log(2 + 1.01 - 1)) + (1 + alpha * 2) / (phi3 * math.log(2 + 1.01 - 2))

        # entropies
        edhh_a_a = col1_metrica / math.exp(phi1 * (2 - 1)) + col2_metrica / math.exp(phi1 * (2 - 2))
        edhh_a_b = col1_metricb / math.exp(phi1 * (2 - 1)) + col2_metricb / math.exp(phi1 * (2 - 2))
        edhh_b_a = col1_metrica / math.exp(phi1 * (2 - 1)) + col2_metrica / math.exp(phi1 * (2 - 2))
        edhh_b_b = col1_metricb / math.exp(phi1 * (2 - 1)) + col2_metricb / math.exp(phi1 * (2 - 2))

        ldhh_a_a = col1_metrica / (phi2 * (2 + 1 - 1)) + col2_metrica / (phi2 * (2 + 1 - 2))
        ldhh_a_b = col1_metricb / (phi2 * (2 + 1 - 1)) + col2_metricb / (phi2 * (2 + 1 - 2))
        ldhh_b_a = col1_metrica / (phi2 * (2 + 1 - 1)) + col2_metrica / (phi2 * (2 + 1 - 2))
        ldhh_b_b = col1_metricb / (phi2 * (2 + 1 - 1)) + col2_metricb / (phi2 * (2 + 1 - 2))

        lgdhh_a_a = col1_metrica / (phi3 * math.log(2 + 1.01 - 1)) + col2_metrica / (phi3 * math.log(2 + 1.01 - 2))
        lgdhh_a_b = col1_metricb / (phi3 * math.log(2 + 1.01 - 1)) + col2_metricb / (phi3 * math.log(2 + 1.01 - 2))
        lgdhh_b_a = col1_metrica / (phi3 * math.log(2 + 1.01 - 1)) + col2_metrica / (phi3 * math.log(2 + 1.01 - 2))
        lgdhh_b_b = col1_metricb / (phi3 * math.log(2 + 1.01 - 1)) + col2_metricb / (phi3 * math.log(2 + 1.01 - 2))

        want = {'FileA': {'DAMBROS_pchu_MetricA': 40 + 10,
                          'DAMBROS_pchu_MetricB': 5 + 7,
                          'DAMBROS_wpchu_MetricA': (1 + alpha * 40) + (1 + alpha * 10),
                          'DAMBROS_wpchu_MetricB': (1 + alpha * 5) + (1 + alpha * 7),
                          'DAMBROS_edpchu_MetricA': edpchu_a_a,
                          'DAMBROS_edpchu_MetricB': edpchu_a_b,
                          'DAMBROS_ldpchu_MetricA': ldpchu_a_a,
                          'DAMBROS_ldpchu_MetricB': ldpchu_a_b,
                          'DAMBROS_lgdpchu_MetricA': lgdpchu_a_a,
                          'DAMBROS_lgdpchu_MetricB': lgdpchu_a_b,

                          'DAMBROS_hh_MetricA': col1_metrica + col2_metrica,
                          'DAMBROS_hh_MetricB': col1_metricb + col2_metricb,
                          'DAMBROS_hwh_MetricA': (40 / 50) * col1_metrica + (10 / 15) * col2_metrica,
                          'DAMBROS_hwh_MetricB': (5 / 15) * col1_metricb + (7 / 9) * col2_metricb,
                          'DAMBROS_edhh_MetricA': edhh_a_a,
                          'DAMBROS_edhh_MetricB': edhh_a_b,
                          'DAMBROS_ldhh_MetricA': ldhh_a_a,
                          'DAMBROS_ldhh_MetricB': ldhh_a_b,
                          'DAMBROS_lgdhh_MetricA': lgdhh_a_a,
                          'DAMBROS_lgdhh_MetricB': lgdhh_a_b,
                          },
                'FileB': {'DAMBROS_pchu_MetricA': 10 + 5,
                          'DAMBROS_pchu_MetricB': 10 + 2,
                          'DAMBROS_wpchu_MetricA': (1 + alpha * 10) + (1 + alpha * 5),
                          'DAMBROS_wpchu_MetricB': (1 + alpha * 10) + (1 + alpha * 2),
                          'DAMBROS_edpchu_MetricA': edpchu_b_a,
                          'DAMBROS_edpchu_MetricB': edpchu_b_b,
                          'DAMBROS_ldpchu_MetricA': ldpchu_b_a,
                          'DAMBROS_ldpchu_MetricB': ldpchu_b_b,
                          'DAMBROS_lgdpchu_MetricA': lgdpchu_b_a,
                          'DAMBROS_lgdpchu_MetricB': lgdpchu_b_b,

                          'DAMBROS_hh_MetricA': col1_metrica + col2_metrica,
                          'DAMBROS_hh_MetricB': col1_metricb + col2_metricb,
                          'DAMBROS_hwh_MetricA': (10 / 50) * col1_metrica + (5 / 15) * col2_metrica,
                          'DAMBROS_hwh_MetricB': (10 / 15) * col1_metricb + (2 / 9) * col2_metricb,
                          'DAMBROS_edhh_MetricA': edhh_b_a,
                          'DAMBROS_edhh_MetricB': edhh_b_b,
                          'DAMBROS_ldhh_MetricA': ldhh_b_a,
                          'DAMBROS_ldhh_MetricB': ldhh_b_b,
                          'DAMBROS_lgdhh_MetricA': lgdhh_b_a,
                          'DAMBROS_lgdhh_MetricB': lgdhh_b_b,
                          }}

        self.maxDiff = None
        self.assertEqual(have, want)
