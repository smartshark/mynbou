#!/usr/bin/env python
# -*- coding: utf-8 -*-

import math
import json
import importlib
import unittest
import datetime

import mongoengine
from bson.objectid import ObjectId

from pycoshark.mongomodels import VCSSystem, Commit, CodeEntityState, File, FileAction, Issue
from mynbou.core import Mynbou


class TestDatabase(unittest.TestCase):
    """Provides integration tests for the Mynbou core.

    This creates a mongomock in-memory database which is fed by json fixtures to set the database to a predefined state.
    Then Mynbou is run and the results for certain metric packages are validated.
    """

    def setUp(self):
        """Setup the mongomock connection."""
        mongoengine.connection.disconnect()
        mongoengine.connect('testdb', host='mongomock://localhost')

    def tearDown(self):
        """Tear down the mongomock connection."""
        mongoengine.connection.disconnect()

    def _load_fixture(self, fixture_name):

        # this would be nice but it does not work
        # db = _get_db()
        # db.connection.drop_database('testdb')

        self._ids = {}
        replace_later = {}

        # we really have to iterate over collections
        for col in ['People', 'Project', 'VCSSystem', 'File', 'Commit', 'FileAction', 'CodeEntityState', 'Hunk', 'Issue', 'IssueSystem', 'Identity']:
            module = importlib.import_module('pycoshark.mongomodels')
            obj = getattr(module, col)
            obj.drop_collection()

        with open('tests/fixtures/{}.json'.format(fixture_name), 'r') as f:
            fixture = json.load(f)
            for col in fixture['collections']:

                module = importlib.import_module('pycoshark.mongomodels')
                obj = getattr(module, col['model'])

                for document in col['documents']:
                    tosave = document.copy()
                    had_id_mapping = False

                    for k, v in document.items():
                        if k == 'id':
                            self._ids[document['id']] = None
                            del tosave['id']
                            had_id_mapping = True
                        if type(v) not in [int, list, dict] and v.startswith('{') and v.endswith('}'):
                            tosave[k] = self._ids[v.replace('{', '').replace('}', '')]

                        if type(v) == list:
                            for sv in v:
                                if type(sv) == str and sv.startswith('{') and sv.endswith('}'):
                                    val = sv.replace('{', '').replace('}', '')
                                    if val not in self._ids.keys():
                                        replace_later[col['model']] = {'field': k, 'value': val}
                                    else:
                                        if type(tosave[k]) == list:
                                            tosave[k][tosave[k].index('{' + val + '}')] = self._ids[val]

                    r = obj(**tosave)
                    r.save()
                    if had_id_mapping:
                        self._ids[document['id']] = r.id

    def test_bug_fixes(self):
        """Utilize the rename_tracking fixture to check if bug-fixes get assigned to the correct file after subsequent renames."""
        self._load_fixture('rename_tracking')

        release = "hash4"
        url = "http://www.github.com/smartshark/visualSHARK"
        project_name = "Testproject"

        ces1 = CodeEntityState.objects.get(s_key="CESFILEARELEASE")
        ces2 = CodeEntityState.objects.get(s_key="CESFILEBRELEASE")
        c = Commit.objects.get(revision_hash=release)
        c.code_entity_states = [ces1.id, ces2.id]
        c.save()

        f1 = File.objects.get(path='D/D.java')
        f2 = File.objects.get(path='B/B.java')

        bugfix_commit = Commit.objects.get(revision_hash='hash5')
        bugfix_commit.fixed_issue_ids = [Issue.objects.get(external_id='IS-1').id]
        bugfix_commit.save()

        bugfix_fa = FileAction.objects.get(commit_id=bugfix_commit.id, file_id=f2.id)

        c1 = Commit.objects.get(revision_hash="hash1")
        fa1 = FileAction.objects.get(commit_id=c1.id, file_id=f1.id)
        fa1.induces = [{"change_file_action_id": bugfix_fa.id, "label": "JLMIV+", "szz_type": "inducing"}]
        fa1.save()

        fa2 = FileAction.objects.get(commit_id=c.id, file_id=f2.id)
        fa2.induces = [{"change_file_action_id": bugfix_fa.id, "label": "JLMIV+", "szz_type": "partial_fix"}]
        fa2.save()

        vcs = VCSSystem.objects.get(url=url)
        m = Mynbou(vcs, project_name, release)
        instances, release_information = m.release()

        # File B/B.java has a bugfix even if it was introduced when its name was still D/D.java
        self.assertEqual(instances['B/B.java']['bug_fixes'][0][0], 'IS-1')

    def test_rename_tracking(self):
        """Simple test for tracking subsequent renames of a file."""
        self._load_fixture('rename_tracking')

        release = "hash4"
        url = "http://www.github.com/smartshark/visualSHARK"
        project_name = "Testproject"

        ces1 = CodeEntityState.objects.get(s_key="CESFILEARELEASE")
        ces2 = CodeEntityState.objects.get(s_key="CESFILEBRELEASE")
        c = Commit.objects.get(revision_hash=release)
        c.code_entity_states = [ces1.id, ces2.id]
        c.save()

        vcs = VCSSystem.objects.get(url=url)
        m = Mynbou(vcs, project_name, release)
        instances, release_information = m.release()

        # in the fixtures B.java is twice renamed, nevertheless it should have the same first occurence as A.java which is never renamed
        # B.java is introduced as D.java and renamed first to C.java then to B.java
        self.assertEqual(instances['A/A.java']['first_occurence'], datetime.datetime(2017, 12, 31, 23, 1, 1))
        self.assertEqual(instances['B/B.java']['first_occurence'], datetime.datetime(2017, 12, 31, 23, 1, 1))

    def test_dambros(self):
        """Test D'Ambros churn and entropy of source code metrics.

        The test calculation is the same as in the unit test in test_change.py but this time we set the database to a certain state
        and use Mynbou directly to collect the data.
        """
        self._load_fixture('dambros_metrics')

        release = "hash4"
        url = "http://www.github.com/smartshark/visualSHARK"
        project_name = "Testproject"

        # we have cross-dependencies so that we have to set this manually after the fixture is loaded
        ces1 = CodeEntityState.objects.get(s_key="CESCOMMIT1FILEA")
        ces2 = CodeEntityState.objects.get(s_key="CESCOMMIT1FILEB")
        ces3 = CodeEntityState.objects.get(s_key="CESCOMMIT2FILEA")
        ces4 = CodeEntityState.objects.get(s_key="CESCOMMIT2FILEB")
        ces5 = CodeEntityState.objects.get(s_key="CESCOMMIT3FILEA")
        ces6 = CodeEntityState.objects.get(s_key="CESCOMMIT3FILEB")
        ces7 = CodeEntityState.objects.get(s_key="CESCOMMIT4FILEA")
        ces8 = CodeEntityState.objects.get(s_key="CESCOMMIT4FILEB")

        ces9 = CodeEntityState.objects.get(s_key="CES2COMMIT4FILEA")
        ces10 = CodeEntityState.objects.get(s_key="CES2COMMIT4FILEB")
        c = Commit.objects.get(revision_hash=release)
        c.code_entity_states = [ces7.id, ces8.id, ces9.id, ces10.id]
        c.save()

        c2 = Commit.objects.get(revision_hash=c.parents[0])
        c2.code_entity_states = [ces5.id, ces6.id]
        c2.save()

        c3 = Commit.objects.get(revision_hash=c2.parents[0])
        c3.code_entity_states = [ces3.id, ces4.id]
        c3.save()

        c4 = Commit.objects.get(revision_hash=c3.parents[0])
        c4.code_entity_states = [ces1.id, ces2.id]
        c4.save()

        vcs = VCSSystem.objects.get(url=url)
        m = Mynbou(vcs, project_name, release)
        instances, release_information = m.release()

        dambros = {}
        for file, values in instances.items():
            dambros[file] = {}

            for metric, value in values.items():
                if metric.startswith('DAMBROS') and metric.endswith(('wmc', 'dit')):
                    dambros[file][metric] = value

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

        want = {'A/A.java': {'DAMBROS_pchu_wmc': 40 + 10,
                             'DAMBROS_pchu_dit': 5 + 7,
                             'DAMBROS_wpchu_wmc': (1 + alpha * 40) + (1 + alpha * 10),
                             'DAMBROS_wpchu_dit': (1 + alpha * 5) + (1 + alpha * 7),
                             'DAMBROS_edpchu_wmc': edpchu_a_a,
                             'DAMBROS_edpchu_dit': edpchu_a_b,
                             'DAMBROS_ldpchu_wmc': ldpchu_a_a,
                             'DAMBROS_ldpchu_dit': ldpchu_a_b,
                             'DAMBROS_lgdpchu_wmc': lgdpchu_a_a,
                             'DAMBROS_lgdpchu_dit': lgdpchu_a_b,

                             'DAMBROS_hh_wmc': col1_metrica + col2_metrica,
                             'DAMBROS_hh_dit': col1_metricb + col2_metricb,
                             'DAMBROS_hwh_wmc': (40 / 50) * col1_metrica + (10 / 15) * col2_metrica,
                             'DAMBROS_hwh_dit': (5 / 15) * col1_metricb + (7 / 9) * col2_metricb,
                             'DAMBROS_edhh_wmc': edhh_a_a,
                             'DAMBROS_edhh_dit': edhh_a_b,
                             'DAMBROS_ldhh_wmc': ldhh_a_a,
                             'DAMBROS_ldhh_dit': ldhh_a_b,
                             'DAMBROS_lgdhh_wmc': lgdhh_a_a,
                             'DAMBROS_lgdhh_dit': lgdhh_a_b,
                             },
                'B/B.java': {'DAMBROS_pchu_wmc': 10 + 5,
                             'DAMBROS_pchu_dit': 10 + 2,
                             'DAMBROS_wpchu_wmc': (1 + alpha * 10) + (1 + alpha * 5),
                             'DAMBROS_wpchu_dit': (1 + alpha * 10) + (1 + alpha * 2),
                             'DAMBROS_edpchu_wmc': edpchu_b_a,
                             'DAMBROS_edpchu_dit': edpchu_b_b,
                             'DAMBROS_ldpchu_wmc': ldpchu_b_a,
                             'DAMBROS_ldpchu_dit': ldpchu_b_b,
                             'DAMBROS_lgdpchu_wmc': lgdpchu_b_a,
                             'DAMBROS_lgdpchu_dit': lgdpchu_b_b,

                             'DAMBROS_hh_wmc': col1_metrica + col2_metrica,
                             'DAMBROS_hh_dit': col1_metricb + col2_metricb,
                             'DAMBROS_hwh_wmc': (10 / 50) * col1_metrica + (5 / 15) * col2_metrica,
                             'DAMBROS_hwh_dit': (10 / 15) * col1_metricb + (2 / 9) * col2_metricb,
                             'DAMBROS_edhh_wmc': edhh_b_a,
                             'DAMBROS_edhh_dit': edhh_b_b,
                             'DAMBROS_ldhh_wmc': ldhh_b_a,
                             'DAMBROS_ldhh_dit': ldhh_b_b,
                             'DAMBROS_lgdhh_wmc': lgdhh_b_a,
                             'DAMBROS_lgdhh_dit': lgdhh_b_b,
                             }}

        self.maxDiff = None
        self.assertEqual(dambros, want)

    def test_change(self):
        """Test Moser and Hassan change metrics."""
        self._load_fixture('change_metrics')

        release = "hash6"
        url = "http://www.github.com/smartshark/visualSHARK"
        project_name = "Testproject"

        # we have cross-dependencies so that we have to set this manually after the fixture is loaded
        c = Commit.objects.get(revision_hash=release)
        ces1 = CodeEntityState.objects.get(s_key="CESFORCOMMIT5FILE1")
        ces2 = CodeEntityState.objects.get(s_key="CESFORCOMMIT5FILE2")
        ces3 = CodeEntityState.objects.get(s_key="CESFORCOMMIT5FILE3")
        c.code_entity_states = [ObjectId(ces1.id), ObjectId(ces2.id), ObjectId(ces3.id)]
        c.save()

        vcs = VCSSystem.objects.get(url=url)
        m = Mynbou(vcs, project_name, release)
        instances, release_information = m.release()

        hassan = {}
        moser = {}
        churn = {}
        for file, values in instances.items():
            hassan[file] = {}
            moser[file] = {}
            churn[file] = {}

            for metric, value in values.items():
                if metric.startswith('HASSAN'):
                    hassan[file][metric] = value
                elif metric.startswith(('MOSER_authors', 'MOSER_weighted_age')):
                    moser[file][metric] = value
                elif metric.startswith(('days_from_release', 'lines_added', 'lines_deleted', 'ages')):
                    churn[file][metric] = value

        # churn checks
        churn_wanted = {'test.java': {'ages': [0, 2, 4, 4, 23],
                                      'days_from_release': [23, 21, 19, 18, 0],
                                      'lines_added': [3, 3, 0, 2, 3],
                                      'lines_deleted': [0, 0, 3, 0, 0]},
                        'test2.java': {'ages': [0, 8, 23],
                                       'days_from_release': [23, 15, 0],
                                       'lines_added': [3, 3, 3],
                                       'lines_deleted': [0, 0, 0]},
                        'test3.java': {'ages': [0],
                                       'days_from_release': [0],
                                       'lines_added': [4],
                                       'lines_deleted': [0]}}

        self.maxDiff = None
        self.assertEqual(churn, churn_wanted)

        # moser calculation
        moser_wanted = {'test.java': {'MOSER_weighted_age': (0 * 3 + 2 * 3 + 4 * 0 + 4 * 2 + 23 * 3) / 11,
                                      'MOSER_authors': 1},
                        'test2.java': {'MOSER_weighted_age': (0 * 3 + 8 * 3 + 23 * 3) / 9,
                                       'MOSER_authors': 1},
                        'test3.java': {'MOSER_weighted_age': (0 * 4) / 4,
                                       'MOSER_authors': 1},
                        }

        # we only want to check for certain things
        check_wanted = ['MOSER_authors', 'MOSER_weighted_age']
        moser_test = {}
        for k, v in moser.items():
            moser_test[k] = {}
            for k2, v2 in v.items():
                if k2 in check_wanted:
                    moser_test[k][k2] = v2

        self.assertEqual(moser_test, moser_wanted)

        # hassan calculation
        phi1 = 1
        phi2 = 1
        phi3 = 1

        # formula for adaptive sizing entropy, this is calculated for the default window size of 14 days
        h1 = -((11 / 17) * math.log(11 / 17, 3) + (6 / 17) * math.log(6 / 17, 3))
        h2 = -((3 / 10) * math.log(3 / 10, 3) + (3 / 10) * math.log(3 / 10, 3) + (4 / 10) * math.log(4 / 10, 3))

        hassan_wanted = {'test.java': {'HASSAN_ldhcm': h1 / (phi2 * (2 + 1 - 1)) + h2 / (phi2 * (2 + 1 - 2)),
                                       'HASSAN_lgdhcm': h1 / (phi3 * math.log(2 + 1.01 - 1)) + h2 / (phi3 * math.log(2 + 1.01 - 2)),
                                       'HASSAN_edhcm': h1 / math.exp(phi1 * (2 - 1)) + h2 / math.exp(phi1 * (2 - 2)),
                                       'HASSAN_whcm': (11 / 17) * h1 + (3 / 10) * h2,
                                       'HASSAN_hcm': h1 + h2},
                         'test2.java': {'HASSAN_ldhcm': h1 / (phi2 * (2 + 1 - 1)) + h2 / (phi2 * (2 + 1 - 2)),
                                        'HASSAN_lgdhcm': h1 / (phi3 * math.log(2 + 1.01 - 1)) + h2 / (phi3 * math.log(2 + 1.01 - 2)),
                                        'HASSAN_edhcm': h1 / math.exp(phi1 * (2 - 1)) + h2 / math.exp(phi1 * (2 - 2)),
                                        'HASSAN_whcm': (6 / 17) * h1 + (3 / 10) * h2,
                                        'HASSAN_hcm': h1 + h2},
                         'test3.java': {'HASSAN_ldhcm': h2 / (phi2 * (1 + 1 - 1)),
                                        'HASSAN_lgdhcm': h2 / (phi3 * math.log(1 + 1.01 - 1)),
                                        'HASSAN_edhcm': h2 / math.exp(phi1 * (1 - 1)),
                                        'HASSAN_whcm': (4 / 10) * h2,
                                        'HASSAN_hcm': h2}}

        self.assertEqual(hassan, hassan_wanted)
