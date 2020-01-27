#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""This module provides Mynbou class which wraps Volg, change metrics and static source code metrics for the release."""
import logging

import networkx as nx
from dateutil.relativedelta import relativedelta

from mynbou.path import Volg
from mynbou.metrics.change import moser, hassan, dambros
from pycoshark.mongomodels import Commit, CodeEntityState, File, CodeGroupState

from mynbou.constants import *


class Mynbou(object):
    """Core Mynbou functionality.

    This class wraps graph construction, Volg, the change metrics implementations and metrics collection.
    """

    def __init__(self, vcs, project_name, release_hash):
        self._log = logging.getLogger(self.__class__.__name__)

        self.project_name = project_name
        self.vcs = vcs
        self.release_hash = release_hash

        self.files = []
        self.graph = None

        self.load_graph()

    def release(self, limit_type):
        """Provide a full release for the project and release hash Mynbou was initialized with.

        This provides every change metric, release metrics and bug fixes.
        """
        self._log.info('starting change metrics')
        v = Volg(self.graph, self.vcs, self.release_hash)
        change_metrics = v.change_metrics()
        self._log.info('finished change metrics')


        if limit_type == 'False':
            self._log.info('loading issues')
            issues = v.issues()
            self._log.info('finished issue loading')
        elif limit_type == 'JL+R':
            self._log.info('loading issues for 6 months after relase')
            issues = v.issues_six_months_szzr()
            self._log.info('finished issue loading')
        elif limit_type == 'SZZ':
            self._log.info('loading issues for 6 months after relase')
            issues = v.issues_six_months_szz()
            self._log.info('finished issue loading')
        else:
            raise Exception('Unknown type {}'.format(limit_type))

        dambros_deltas = v.dambros_deltas()

        # D'Ambros debugging only
        # with open('dambros_test.json', 'w') as f:
        #     json.dump(dambros_deltas, f, sort_keys=True, indent=4)

        # with open('dambros_test2.json', 'w') as f:
        #     json.dump(v._dambros_values, f, sort_keys=True, indent=4)

        release = {}
        for file in change_metrics.keys():
            release[file] = change_metrics[file]

            if file in issues.keys():
                release[file]['bug_fixes'] = issues[file]

        hassan_metrics = hassan(release)
        moser_metrics = moser(release)
        dambros_metrics = dambros(release, dambros_deltas)

        for file in change_metrics.keys():
            release[file].update(**hassan_metrics[file])
            release[file].update(**moser_metrics[file])
            release[file].update(**dambros_metrics[file])

            # fetch additional release centric metrics
            release[file].update(**self._file_metrics(file, self.release_hash))

        # meta information about the mined release and its path, including which commits are included
        change_path_commits = set()
        for path in v._change_paths:
            for commit in path:
                change_path_commits.add(commit)

        release_information = {'change_path_commits': change_path_commits,
                               'change_path_cutoff_date': str(v._release_date - relativedelta(months=6)),
                               'release_revision': self.release_hash,
                               'release_date': str(v._release_date),
                               }

        return release, release_information

    def load_graph(self):
        """Load NetworkX digraph structure from commits of this VCS."""
        g = nx.DiGraph()
        # first we add all nodes to the graph
        for c in Commit.objects.only('id', 'revision_hash').timeout(False).filter(vcs_system_id=self.vcs.id):
            g.add_node(c.revision_hash)

        # after that we draw all edges
        for c in Commit.objects.only('id', 'parents', 'revision_hash').timeout(False).filter(vcs_system_id=self.vcs.id):
            for p in c.parents:
                try:
                    p1 = Commit.objects.only('id', 'revision_hash').timeout(False).get(vcs_system_id=self.vcs.id, revision_hash=p)
                    g.add_edge(p1.revision_hash, c.revision_hash)
                except Commit.DoesNotExist:
                    print("parent of a commit is missing (commit id: {} - revision_hash: {})".format(c.id, p))
                    pass
        self.graph = g

    def _package_metrics(self, commit, ces_file):
        """Return package metrics from given CodeEntityState of type file.

        Matches classes possibly contained in the current file by using the filename and the file path (agains the package of the class).
        Then loads the metrics from the corresponding package (CodeGroupState).
        """
        metrics = {}
        class_name = ces_file.long_name.split('/')[-1].split('.')[0]
        for ces_class in CodeEntityState.objects.filter(id__in=commit.code_entity_states, long_name__contains=class_name, ce_type__in=['class', 'interface', 'enum']):
            package_name = '.'.join(ces_class.long_name.split('.')[0:-1])

            # check if package from class is the end of our file_path, if not skip to the next class contained in our file
            path = '.'.join(ces_file.long_name.split('/')[0:-1])
            if not path.endswith(package_name):
                continue

            # check if class actually has a package
            if not package_name:
                continue

            # fetch package for our package_name, throw error if not exactly one is found
            cgs = CodeGroupState.objects.get(commit_id=commit.id, cg_type='package', long_name=package_name)
            for k, v in cgs.metrics.items():
                if k in IGNORE_PACKAGE_METRICS:
                    continue
                if k.endswith(' Rules'):
                    pass
                    # metrics['PMD_package_{}'.format(k.lower())] = v
                else:
                    metrics['SM_package_{}'.format(k.lower())] = v
        return metrics

    def _file_metrics(self, filename, commit):
        """Return static source code metrics for the given file and commit (usually the release)."""
        c = Commit.objects.get(revision_hash=commit, vcs_system_id=self.vcs.id)
        f = File.objects.get(vcs_system_id=c.vcs_system_id, path=filename)

        ret = {}
        file = False
        for m in CodeEntityState.objects.filter(id__in=c.code_entity_states, file_id=f.id):

            if m.ce_type == 'file':

                # just a quick sanity check
                if file:
                    raise Exception('2 files in CodeEntityStates for {}'.format(f.path))
                file = True

                for k, v in m.metrics.items():

                    if k in JAVA_NODE_TYPES or k == 'node_count':
                        k = 'AST_{}'.format(k.lower())
                    else:
                        k = 'SM_{}_{}'.format(m.ce_type, k.lower())
                    ret[k] = v

                # ret.update(**m.metrics)
                ret['imports'] = m.imports  # raw imports

                # package metrics
                ret.update(**self._package_metrics(c, m))

                # linter warnings
                for line in m.linter:
                    for k, v in line.items():
                        if k != 'l_ty':
                            continue

                        if v not in ret.keys():
                            ret[v] = 0
                        ret[v] += 1

            else:
                # add scope and make a list, we may have more than one classe/interface/method per file
                for k, metric in m.metrics.items():

                    if k in JAVA_NODE_TYPES:
                        k = 'AST_{}'.format(k.lower())
                    else:
                        k = 'SM_{}_{}'.format(m.ce_type, k.lower())

                    # we are dropping all the rules from Sourcemeter
                    if k.endswith('rules'):
                        continue
                    if k not in ret.keys():
                        ret[k] = []
                    ret[k].append(metric)
        return ret
