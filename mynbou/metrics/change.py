#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This module contains functions for calculation of change metrics.

For now this contains change metrics as as proposed by Moser et al. :cite:`moser`, Hassan :cite:`hassan` and the extensions proposed by D'Ambros et al. :cite:`dambros`.
"""

import math
from mynbou.aggregation import msum


def hassan(instances, window_size_days=14, phi1=1, phi2=1, phi3=1):
    """Calculate Hassan complexity of change metrics with the additon from D'Ambros.

    The addition includes not only if the file has changed
    but also the number of lines (added + deleted).
    Requires the following lists in the dict: lines_added, lines_deleted, days_from_release (list of days before release where the file changed).

    :param dict instances: dict with structure {'filepath': {'lines_added': [1,2], ...}}.
    :param int window_size_days: window size in days
    :param float phi1: decay factor
    :param float phi2: decay factor
    :param float phi3: decay factor
    :rtype: dict
    :returns: dict with key filepath and values change metrics
    """
    rel = {}

    # sum of changed lines and max age for temporal slicing
    max_age = 0
    all_changed_lines = 0
    days = {}

    n = instances.keys()  # all files in the system
    n_bar = set()  # all files changed in the current period (e.g., 6 months not window_size!)
    for file, metrics in instances.items():

        # this creates basically a lookup table of day -> list of files
        for day in set(metrics['days_from_release']):
            if day not in days.keys():
                days[day] = []
            days[day].append(file)
            n_bar.add(file)

        # find max age used for the range calculation later
        # ages can be empty if the file was never changed in our current mining path
        if metrics['days_from_release'] and max(metrics['days_from_release']) > max_age:
            max_age = max(metrics['days_from_release'])
        # find all changed lines over the complete release
        all_changed_lines += sum(metrics['lines_added']) + sum(metrics['lines_deleted'])

    n_bar = len(n_bar)  # we just need the number of files changed in the change path

    # 1. create a range of days with window_size_days 14 (2 weeks)
    # if our date range is not exactly divisible by 14 we do not use the surplus days at the beginning because the days at
    # the end of the date range are probably more important (closer to release == 0)
    start = 0
    end = max_age + (max_age % window_size_days)
    a = list(reversed(range(start, end, window_size_days)))

    # weighted history of complexity metric per file
    whcm = {}

    # for the history of complexity metric and the version with decay calculation
    # we could in theory also use the weighted variant for these but for now we are using the unweighted version as in D'Ambros et al.
    hcm = {}

    # list of weeks per file, this is just for debugging purposes
    weeks_list = {}

    # 2. find all changes for this daterange (1 week) zip(a[:-1], a[1:]) == (0,7) (7,14) ...
    # we switch this around as we may have decaying factors so first is oldest instead of most recent (therefore a[1:], a[:-1])
    for i, j in zip(a[1:], a[:-1]):

        # find every file that has changed in the date range
        files = {}

        # all lines changed in the daterange
        all_changed_lines = 0

        # we need this for the weighting part
        all_changed_files = 0

        # for each day of the week (range(0,7) == [0,1,2,3,4,5,6])
        for day in range(i, j):

            # if nothing was changed on that day, continue
            if day not in days.keys():
                continue

            # every file that is changed on that day
            for file in days[day]:

                if file not in weeks_list.keys():
                    weeks_list[file] = []

                if (i, j) not in weeks_list[file]:
                    weeks_list[file].append((i, j))

                if file not in files.keys():
                    files[file] = {'changed_lines': []}

                # 2.1 find changeset for this day, we can do this here because Volg uses lists (which preserve order)
                # idx = instances[file]['ages'].index(day)  # this does not work if we have two commits on one day

                # this is more expensive but works for more than one commit on a given day
                for idx in [idx for idx, value in enumerate(instances[file]['days_from_release']) if value == day]:
                    la = instances[file]['lines_added'][idx]
                    ld = instances[file]['lines_deleted'][idx]

                    files[file]['changed_lines'].append(la + ld)
                    all_changed_lines += la + ld

                    # we need to count every change to every file for the weighting
                    all_changed_files += 1

        # adaptive sizing entropy for this period, we use a list because we need to sort the values later
        ase = []
        # we could iterate over all files directly but files not changed in this date range would yield p=0 anyway
        for file, dat in files.items():

            # IMPORTANT: if only one file is changed in the given date range we would have log to the base of 1
            # as this is an entropy based formula we set it to 0
            # same as when 0 lines are changed
            if n_bar > 1 and all_changed_lines > 0:
                p = sum(dat['changed_lines']) / all_changed_lines
                if p > 0:
                    ase.append(-p * math.log(p, n_bar))

        for file, dat in files.items():
            # history of complexity metric, we append the ASE of this period if this file was changed in this period
            if file not in hcm.keys():
                hcm[file] = []
            hcm[file].append(msum(sorted(ase)))

            # weighted history of complexity metric
            # we weight by number of changes of file for given date range / number of all changes for given date range
            # the number of changes we can get by looking at the length of the changed_lines list
            if file not in whcm.keys():
                whcm[file] = []
            
            if all_changed_lines > 0:
                whcm[file].append((sum(dat['changed_lines']) / all_changed_lines) * msum(sorted(ase)))

    # now get the real values for the decay of the files from our pre-filled hcm list
    ldhcm = {}
    lgdhcm = {}
    edhcm = {}

    # decay factors
    phi1 = 1
    phi2 = 1
    phi3 = 1

    for file in hcm.keys():

        if file not in ldhcm.keys():
            ldhcm[file] = []
            lgdhcm[file] = []
            edhcm[file] = []

        all_changes = len(hcm[file])
        for pos, hcmval in enumerate(hcm[file]):
            pos = pos + 1  # we are not starting from zero, otherwise + 1 would not make much sense
            ldhcm[file].append(hcmval / (phi1 * (all_changes + 1 - pos)))
            lgdhcm[file].append(hcmval / (phi2 * (math.log(all_changes + 1.01 - pos))))
            edhcm[file].append(hcmval / (math.exp(phi3 * (all_changes - pos))))

    for file in instances.keys():

        if file not in rel.keys():
            # defaults if a file has not changed in our inspection period
            rel[file] = {'HASSAN_ldhcm': 0, 'HASSAN_lgdhcm': 0, 'HASSAN_edhcm': 0, 'HASSAN_hcm': 0, 'HASSAN_whcm': 0}

        # if file in weeks_list.keys():  # debug
        #     rel[file]['HASSAN_weeks'] = weeks_list[file]

        if file in ldhcm.keys():
            rel[file]['HASSAN_ldhcm'] = msum(sorted(ldhcm[file]))
            rel[file]['HASSAN_lgdhcm'] = msum(sorted(lgdhcm[file]))
            rel[file]['HASSAN_edhcm'] = msum(sorted(edhcm[file]))

        if file in hcm.keys():
            rel[file]['HASSAN_hcm'] = msum(sorted(hcm[file]))

        if file in whcm.keys():
            rel[file]['HASSAN_whcm'] = msum(sorted(whcm[file]))

    return rel


def moser(instances):
    """Calculate change metrics after Moser et al.

    Requires the following lists in the dict: authors, revisions, lines_added, lines_deleted, changesets, commit_messages, ages (list of days after start where the file changed).

    Requires the following additional fields in the dict: age (date from the end of metrics selection to the first appearance of the file in days)

    :param dict instances: dict with structure {'filepath': {'lines_added': [1,2], ...}}.
    :rtype: dict
    :returns: dict with key filepath and values change metrics
    """
    rel = {}
    for file in instances.keys():
        rel[file] = {
            'MOSER_authors': len(set(instances[file]['authors'])),
            'MOSER_revisions': len(instances[file]['revisions']),
            'MOSER_sum_lines_added': sum(instances[file]['lines_added']),
            'MOSER_max_lines_added': max(instances[file]['lines_added'], default=0),
            'MOSER_avg_lines_added': 0,
            'MOSER_sum_lines_deleted': sum(instances[file]['lines_deleted']),
            'MOSER_max_lines_deleted': max(instances[file]['lines_deleted'], default=0),
            'MOSER_avg_lines_deleted': 0,
            'MOSER_sum_code_churn': sum(instances[file]['lines_added']) - sum(instances[file]['lines_deleted']),
            # pairwise churn for finding max
            'MOSER_max_code_churn': max([la - ld for la, ld in zip(instances[file]['lines_added'], instances[file]['lines_deleted'])], default=0),
            'MOSER_avg_code_churn': 0,
            'MOSER_max_changeset': max(instances[file]['changesets'], default=0),
            'MOSER_avg_changeset': 0,

            # moser_refactorings (ILIKE '%refactor%')
            'MOSER_refactorings': sum([1 if 'refactor' in c.lower() else 0 for c in instances[file]['commit_messages']]),

            # moser_bugfix (ILIKE '%Fix%' AND NOT ILIKE '% prefix %' AND NOT ILIKE '% postfix %')
            'MOSER_bugfix': sum([1 if 'fix' in c.lower() and ' prefix ' not in c.lower() and ' postfix ' not in c.lower() else 0 for c in instances[file]['commit_messages']]),
            'MOSER_age': instances[file]['age'],  # date from end of metrics selection to first appearence of file in days
            'MOSER_weighted_age': 0
        }

        # weighted age is age wighted by changes to the file
        if sum(instances[file]['lines_added']) > 0:
            rel[file]['MOSER_weighted_age'] = sum([a * b for a, b in zip(instances[file]['ages'], instances[file]['lines_added'])]) / sum(instances[file]['lines_added'])

        if len(instances[file]['revisions']) > 0:
            tmp = {'MOSER_avg_lines_added': sum(instances[file]['lines_added']) / len(instances[file]['revisions']),
                   'MOSER_avg_lines_deleted': sum(instances[file]['lines_deleted']) / len(instances[file]['revisions']),
                   'MOSER_avg_code_churn': (sum(instances[file]['lines_added']) - sum(instances[file]['lines_deleted'])) / len(instances[file]['revisions']),
                   'MOSER_avg_changeset': sum(instances[file]['changesets']) / len(instances[file]['revisions'])}
            rel[file].update(**tmp)
    return rel


def dambros(instances, deltas, alpha=0.01, phi1=1, phi2=1, phi3=1):
    """Calculate D'Ambros et al. churn of source code metrics and entropy of source code metrics.

    In contrast to D'Ambros et al. who used multiple delta matrices we are using just one with an additional dimension of filepath.

    :param dict instances: dict with structure {'filepath': {'metric1': [1,2], ...}}. Only the filepath as key is needed here.
    :param dict deltas: dict with structure {'metric1': {'filepath': [deltavalue1, deltavalue2, ...]}}
    :param float phi1: decay factor
    :param float phi2: decay factor
    :param float phi3: decay factor
    :rtype: dict
    :returns: dict with key filepath and values change metrics
    """
    rel = {}

    # sum up the deltas for each file over one timestep
    sum_rows = {}
    R_j = {}
    entropy_h = {}

    # we need sum of columns also per metric
    for metric in deltas.keys():

        if metric not in sum_rows.keys():
            sum_rows[metric] = {}

        if metric not in entropy_h.keys():
            R_j[metric] = {}

        for file in deltas[metric].keys():
            for j, value in enumerate(deltas[metric][file]):

                absval = abs(value)
                # add every value > 0
                if value != -1 and value != 0:
                    if j not in sum_rows[metric].keys():
                        sum_rows[metric][j] = []
                    if j not in R_j[metric].keys():
                        R_j[metric][j] = 0

                    # number of values greater than 0
                    R_j[metric][j] += 1
                    sum_rows[metric][j].append(absval)  # sum of values greater than 0 for each timestep over all classes

    # entropy for every column (still over all files)
    for metric in deltas.keys():

        if metric not in entropy_h.keys():
            entropy_h[metric] = {}

        for file in deltas[metric].keys():
            for j, value in enumerate(deltas[metric][file]):

                absval = abs(value)

                if value != -1 and value != 0:
                    if j not in entropy_h[metric].keys():
                        entropy_h[metric][j] = []
                    p = absval / sum(sum_rows[metric][j])

                    # IMPORTANT: if we end up with a base of 0 or 1 for log we are not adding the value to the summation list
                    # as this is an entropy based formula
                    if R_j[metric][j] > 1 and p > 0:
                        entropy_h[metric][j].append(-p * math.log(p, R_j[metric][j]))

    for file in instances.keys():
        churns = {}
        entropy = {}
        for m in deltas.keys():
            pchu = 'DAMBROS_pchu_{}'.format(m)
            wpchu = 'DAMBROS_wpchu_{}'.format(m)
            edpchu = 'DAMBROS_edpchu_{}'.format(m)
            ldpchu = 'DAMBROS_ldpchu_{}'.format(m)
            lgdpchu = 'DAMBROS_lgdpchu_{}'.format(m)

            hh = 'DAMBROS_hh_{}'.format(m)
            hwh = 'DAMBROS_hwh_{}'.format(m)
            edhh = 'DAMBROS_edhh_{}'.format(m)
            ldhh = 'DAMBROS_ldhh_{}'.format(m)
            lgdhh = 'DAMBROS_lgdhh_{}'.format(m)

            churns[pchu] = []
            churns[wpchu] = []
            churns[edpchu] = []
            churns[ldpchu] = []
            churns[lgdpchu] = []

            entropy[hh] = []
            entropy[hwh] = []
            entropy[edhh] = []
            entropy[ldhh] = []
            entropy[lgdhh] = []

            if file not in deltas[m].keys():
                raise Exception('Could not find file: {} in deltas!'.format(file))

            C = len(deltas[m][file])  # number of columns of the matrix (timesteps)

            # churn of source code metrics
            for j, value in enumerate(deltas[m][file]):
                if value != -1 and value != 0:
                    absval = abs(value)
                    pos = j + 1
                    churns[pchu].append(absval)
                    churns[wpchu].append(1 + alpha * absval)
                    churns[edpchu].append((1 + alpha * absval) / (math.exp(phi1 * (C - pos))))
                    churns[ldpchu].append((1 + alpha * absval) / (phi2 * (C + 1 - pos)))
                    churns[lgdpchu].append((1 + alpha * absval) / (phi3 * math.log(C + 1.01 - pos)))

            # entropy of source code metrics
            for j, value in enumerate(deltas[m][file]):
                if value != -1 and value != 0:
                    pos = j + 1
                    p = abs(value) / sum(sum_rows[m][j])
                    sum_j = sum(entropy_h[m][j])
                    entropy[hh].append(sum_j)
                    entropy[hwh].append(p * sum_j)
                    entropy[edhh].append(sum_j / (math.exp(phi1 * (C - pos))))
                    entropy[ldhh].append(sum_j / (phi2 * (C + 1 - pos)))
                    entropy[lgdhh].append(sum_j / (phi3 * math.log(C + 1.01 - pos)))

        # sum up everything and report back
        rel[file] = {k: msum(v) for k, v in churns.items()}
        rel[file].update(**{k: msum(v) for k, v in entropy.items()})

    return rel
