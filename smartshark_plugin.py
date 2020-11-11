#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""This module provides the SmartSharkPlugin class which wraps Mynbou, logging, pycoshark and aggregations.

It provides cleaned and harmonized instances that are then saved to files.
"""
import sys
import logging
import json
import timeit
import math
import datetime

from pycoshark.mongomodels import Project, VCSSystem, MynbouData
from pycoshark.utils import create_mongodb_uri_string
from pycoshark.utils import get_base_argparser

from mongoengine import connect

from mynbou.core import Mynbou
from mynbou.constants import *
from mynbou import aggregation

log = logging.getLogger()
log.setLevel(logging.INFO)
# i = logging.StreamHandler(sys.stdout)
# e = logging.StreamHandler(sys.stderr)

# i.setLevel(logging.INFO)
# e.setLevel(logging.ERROR)

# log.addHandler(i)
# log.addHandler(e)


class SmartsharkPlugin(object):
    """Use metrics and issues from SmartSHARK Database."""

    def __init__(self, args):
        self._log = logging.getLogger(self.__class__.__name__)
        self.release_name = args.release_name
        self.args = args

    def _clean_instances(self, instances):
        cleaned_instances = []
        for file, vector in instances.items():
            tmp = vector

            del tmp['first_occurence']  # datetime object no longer needed
            # del tmp['weeks']  # debug data no longer needed
            del tmp['authors']  # list of names, we don't want that

            # remove base attributes that were used to calculate new ones
            del tmp['aliases']
            del tmp['age']
            # del tmp['ages']
            # del tmp['days_from_release']
            del tmp['changesets']
            del tmp['lines_added']
            del tmp['lines_deleted']
            # del tmp['imports']  # we change this later to a comma separated string
            # del tmp['revisions']
            del tmp['commit_messages']

            tmp['file'] = file
            cleaned_instances.append(tmp)
        return cleaned_instances

    def _bug_info(self, cleaned_instances):
        bug_info = []
        for instance in cleaned_instances:

            bfdata = []
            for iss in instance['bug_fixes']:
                new_bug = {'name': iss[0], 'severity': iss[3], 'type': iss[4], 'bugfix_commit': iss[2], 'bugfix_commit_date': iss[1], 'issue_created_at': iss[5]}
                if new_bug not in bfdata:
                    bfdata.append(new_bug)
            bug_info.append({'file': instance['file'], 'bug_fixes': bfdata})
        return bug_info

    def _harmonize_instances(self, cleaned_instances):
        # aggregate static soucre code metrics where it makes sense
        bug_fixes = {}
        aggregated_instances = []
        latest_bugfix = {}

        for instance in cleaned_instances:
            inst = {}
            for k, v in instance.items():
                # create issue matrix
                if k.startswith('bug_fixes'):
                    # this just creates a list of bugfix commits for each issue found
                    # we need this to get the max() of bugfix_commit_date
                    for prei in v:
                        if prei[0] not in latest_bugfix.keys():
                            latest_bugfix[prei[0]] = []
                        latest_bugfix[prei[0]].append(prei[1])

        for instance in cleaned_instances:
            inst = {}
            for k, v in instance.items():

                # skip our debug values
                if k in ['ages', 'revisions', 'changesets', 'commit_messages', 'days_from_release']:
                    continue

                # skip values which are NaN
                if k in ['SM_method_hcpl', 'SM_method_heff', 'SM_method_htrp', 'SM_method_hvol', 'SM_method_hndb']:
                    continue

                key = k

                # create issue matrix
                if k.startswith('bug_fixes'):
                    inst['BUGFIX_issues'] = []
                    unique_ids = set()
                    for iss in v:  # tuple is like this: (id, commitdate, revision hash, priority, type)
                        inst['BUGFIX_issues'].append({'name': iss[0], 'severity': iss[3], 'type': iss[4], 'bugfix_commit': iss[2], 'bugfix_commit_date': iss[1], 'created_at': iss[5]})
                        unique_ids.add(iss[0])

                        if instance['file'] not in bug_fixes.keys():
                            bug_fixes[instance['file']] = set()

                        issue_name = '{}_{}_{}'.format(iss[0], iss[3], max(latest_bugfix[iss[0]]))
                        bug_fixes[instance['file']].add(issue_name)
                        inst[issue_name] = 1
                    inst['BUGFIX_count'] = len(set(unique_ids))

                # count all refactorings
                elif k == 'refactorings':
                    for ref in v:
                        ref_name = 'REFACTOR_{}'.format(ref)
                        if ref_name not in inst.keys():
                            inst[ref_name] = 0
                        inst[ref_name] += 1

                # count all change types
                elif k.startswith('change_types'):
                    for change_dict in v:
                        for change_type, change_count in change_dict.items():
                            change_name = 'CHANGE_TYPE_{}'.format(change_type.lower())
                            if change_name not in inst.keys():
                                inst[change_name] = 0
                            inst[change_name] += change_count

                elif k.startswith(('SM_method', 'SM_interface', 'SM_enum', 'SM_class', 'SM_annotation')):  # and isinstance(v, list):  # everything in ce_type file is not a list because we only have one

                    if isinstance(v, list):
                        v2 = v
                    else:
                        v2 = [v]
                    # special aggregations for method level to file level
                    # if k.startswith('SM_method'):
                    for value in v2:
                        if math.isnan(value):
                            self._log.error('value is NaN for {} in file {}'.format(k, instance['file']))
                    inst[k + '_sum'] = sum(v2)
                    inst[k + '_min'] = min(v2)
                    inst[k + '_max'] = max(v2)
                    inst[k + '_avg'] = sum(v2) / len(v2)  # we only have this k if we have at least one element in the list
                    inst[k + '_median'] = 0
                    inst[k + '_stdev'] = 0
                    inst[k + '_coefficient_of_variation'] = 0
                    inst[k + '_gini'] = 0
                    inst[k + '_hoover'] = 0
                    inst[k + '_atkinson'] = 0
                    inst[k + '_shannon_entropy'] = 0
                    inst[k + '_generalized_entropy'] = 0
                    inst[k + '_theil'] = 0
                    if len(v2) > 0:
                        inst[k + '_median'] = aggregation.median(v2)
                        inst[k + '_stdev'] = aggregation.stddev(v2)
                        inst[k + '_coefficient_of_variation'] = aggregation.cov(v2)
                        inst[k + '_gini'] = aggregation.gini(v2)
                        inst[k + '_hoover'] = aggregation.hoover(v2)
                        inst[k + '_atkinson'] = aggregation.atkinson(v2)
                        inst[k + '_shannon_entropy'] = aggregation.shannon_entropy(v2)
                        inst[k + '_generalized_entropy'] = aggregation.generalized_entropy(v2)
                        inst[k + '_theil'] = aggregation.theil(v2)

                # collect severities
                elif k.startswith('PMD') and not k.startswith('PMD_severity_') and not k.startswith('PMD_rule_type_') and not k.startswith('PMD_package'):
                    # create keys for all severities
                    for sev in PMD_SEVERITIES:
                        key = 'PMD_severity_{}'.format(sev.lower())
                        if key not in inst.keys():
                            inst[key] = 0

                    for rt in PMD_RULE_TYPES:
                        key = 'PMD_rule_type_{}'.format(rt.lower())
                        if key not in inst.keys():
                            inst[key] = 0

                    # count rule violation towards its severity
                    inst['PMD_severity_' + PMD_RMATCH[k].lower()] += 1

                    # count rule violations toward its rule type
                    inst['PMD_rule_type_' + PMD_RTMATCH[k].lower()] += 1

                    # also set normal counts for PMD Linter
                    tmp = k.split('_')
                    inst['_'.join(tmp[0:-1]) + '_' + tmp[-1].lower()] = v

                elif k == 'linked_issues':

                    # make this unique quickly per file
                    linked_issues = set()
                    for i in v:
                        linked_issues.add('{}_{}_{}'.format(i['priority'], i['issue_type'], i['external_id']))

                    for issue in linked_issues:  # we only count each issue once
                        issue_severity, issue_type, issue_id = issue.split('_')

                        itype = str(issue_type).lower().strip()
                        if itype in TICKET_TYPE_MAPPING.keys():
                            itype = TICKET_TYPE_MAPPING[itype]
                        else:
                            itype = 'other'

                        iseverity = str(issue_severity).lower().strip()
                        if iseverity not in TICKET_SEVERITIES:
                            iseverity = 'other'

                        key = 'ISSUE_{}_{}'.format(iseverity, itype)
                        if key not in inst.keys():
                            inst[key] = 0
                        inst[key] += 1
                elif k == 'imports':
                    inst[k] = ','.join(v)
                else:
                    inst[k] = v

            aggregated_instances.append(inst)

        # we build a list of all available metrics and set their value to 0 if they are not in the instance
        keys = []
        for key in SM_METRICS + CLONE_METRICS:

            # skip values which are NaN
            if key in ['SM_method_hcpl', 'SM_method_heff', 'SM_method_htrp', 'SM_method_hvol', 'SM_method_hndb']:
                continue

            if key.startswith(('SM_method', 'SM_interface', 'SM_enum', 'SM_class', 'SM_annotation')):
                keys.append(key + '_sum')
                keys.append(key + '_min')
                keys.append(key + '_max')
                keys.append(key + '_avg')
                keys.append(key + '_median')
                keys.append(key + '_stdev')
                keys.append(key + '_coefficient_of_variation')
                keys.append(key + '_gini')
                keys.append(key + '_hoover')
                keys.append(key + '_atkinson')
                keys.append(key + '_shannon_entropy')
                keys.append(key + '_generalized_entropy')
                keys.append(key + '_theil')
            else:
                keys.append(key)

        # build PMD keys for abbrevs and also for severities
        for key in PMD_RMATCH.keys():
            tmp = key.split('_')
            keys.append('_'.join(tmp[:-1]) + '_' + tmp[-1].lower())

        for key in list(set(PMD_RMATCH.values())):
            keys.append('PMD_severity_' + key.lower())

        # PMD rule types
        for key in PMD_RULE_TYPES:
            keys.append('PMD_rule_type_' + key.lower())

        # commit change tpye
        for change_type in CHANGE_TYPES:
            change_name = 'CHANGE_TYPE_{}'.format(change_type.lower())
            keys.append(change_name)

        # refactoring types
        for key in REFACTORING_TYPES:
            keys.append('REFACTOR_{}'.format(key))

        # ticket severities
        for key in TICKET_SEVERITIES + ['other']:
            for key2 in set(TICKET_TYPE_MAPPING.values()):
                keys.append('ISSUE_{}_{}'.format(key.lower(), key2.lower()))

        # java node types (we should have these for every file)
        for key in JAVA_NODE_TYPES:
            keys.append('AST_{}'.format(key.lower()))

        # we also add keys present in every instance (change, bug_fix, etc.)
        # this allows us to add this without having extra definitions for these
        # print('aggregated keys', aggregated_instances[0].keys())
        for key in aggregated_instances[0].keys():
            if key not in keys:
                # print('adding', key)
                keys.append(key)

        # filter our keys for stuff we do not want in aggregated but exist in every instance
        for remove in ['refactorings', 'bug_fixes', 'change_types', 'BUGFIX_issues']:
            if remove in keys:
                keys.remove(remove)

        # bug fixes matrix
        for issues in bug_fixes.values():
            for issue in issues:
                keys.append(issue)

        harmonized_instances = []
        for instance in aggregated_instances:
            inst = {}
            for k in keys:
                if k not in instance.keys():
                    inst[k] = 0
                else:
                    inst[k] = instance[k]
            harmonized_instances.append(inst)

        return harmonized_instances, bug_fixes, keys

    def start_mining(self, release):
        start = timeit.default_timer()

        project_id = Project.objects.get(name=self.args.project_name).id
        self.vcs = VCSSystem.objects.get(project_id=project_id)

        m = Mynbou(self.vcs, self.args.project_name, release)
        instances, release_information = m.release(self.args.type)

        base_file_name = self.release_name
        if self.args.type != 'False':
            base_file_name = '{}_{}'.format(self.release_name, self.args.type)

        if not instances:
            raise Exception('No instances extracted for this release')

        # write full file with only cleaned instances
        cleaned_instances = self._clean_instances(instances)
        data = {'release_date': release_information['release_date'],
                'instances': cleaned_instances}
        with open(base_file_name + '.json', 'w') as outfile:
            json.dump(data, outfile, sort_keys=True, indent=4)

        # information about bug_fixes written to extra file
        bug_info = self._bug_info(cleaned_instances)
        with open(base_file_name + '_bug_fixes.json', 'w') as outfile:
            json.dump(bug_info, outfile, sort_keys=True, indent=4)

        # harmonize instances and get keys from harmonization, they are later used to provide a header for the csv file
        harmonized_instances, bug_fixes, keys = self._harmonize_instances(cleaned_instances)

        # write new aggregated data
        data['instances'] = harmonized_instances
        if self.args.generate_json.lower() != "false" or self.args.save_to_mongo:
            with open(base_file_name + '_aggregated.json', 'w') as outfile:
                json.dump(data, outfile, sort_keys=True, indent=4)

        # create csv, bugfix_count and matrix at the end
        # make sure the BUGFIX_count and issue matrix are at the end
        header = sorted(list(set(keys)))
        header.remove('file')
        header.remove('BUGFIX_count')
        for issue in bug_fixes.values():
            if type(issue) == set:
                for i in issue:
                    if i in header:
                        header.remove(i)
            else:
                if issue in header:
                    header.remove(issue)

        header = ['file'] + header
        header.append('BUGFIX_count')
        for issue in bug_fixes.values():
            if type(issue) == set:
                for i in issue:
                    if i not in header:
                        header.append(i)
            else:
                if i not in header:
                    header.append(issue)

        with open(base_file_name + '_aggregated.csv', 'w') as outfile:
            outfile.write(';'.join(header) + '\n')

            for instance in harmonized_instances:
                inst = []
                for key in header:
                    inst.append(instance[key])
                outfile.write(';'.join([str(i) for i in inst]) + '\n')

        # upload to mynbou data
        if self.args.save_to_mongo:
            try:
                m = MynbouData.objects.get(vcs_system_id=self.vcs.id, name=self.release_name, path_approach='default', bugfix_label=self.args.type, metric_approach='default')
            except MynbouData.DoesNotExist:
                m = MynbouData(vcs_system_id=self.vcs.id, name=self.release_name, path_approach='default', bugfix_label=self.args.type, metric_approach='default')

            if m.file:
                m.file.delete()
            m.last_updated = datetime.datetime.now()
            m.save()
            with open(base_file_name + '_aggregated.json', 'rb') as fd:
                m.file.put(fd, content_type='application/json')
            m.save()

        end = timeit.default_timer() - start
        log.info("Finished mynbou in {:.5f}s".format(end))


def main(args):
    if args.log_level and hasattr(logging, args.log_level):
        log.setLevel(getattr(logging, args.log_level))

    uri = create_mongodb_uri_string(args.db_user, args.db_password, args.db_hostname, args.db_port, args.db_authentication, args.ssl)
    connect(args.db_database, host=uri)

    c = SmartsharkPlugin(args)
    c.start_mining(args.release_commit)


if __name__ == '__main__':
    parser = get_base_argparser('Analyze the given URI. An URI should be a GIT Repository address.', '1.0.0')

    parser.add_argument('-pn', '--project-name', help='Name of the project.', required=True)
    parser.add_argument('-rn', '--release-name', help='Name of the release to be mined.', required=True)
    parser.add_argument('-tr', '--release-commit', help='Target release.', required=True)
    parser.add_argument('-tp', '--type', help='Limit window after release for bug-fixing commits to be considered to 6 months.', default='False')
    parser.add_argument('-ll', '--log-level', help='Log level for stdout (DEBUG, INFO), default INFO', default='INFO')
    parser.add_argument('-gs', '--generate-json', help='Indicate if an additional aggregated JSON file should be generated (True, False).', default='False')
    parser.add_argument('--save-to-mongo', help='Save result to MongoDB', action='store_true')

    main(parser.parse_args())
