# mynbou

[![Build Status](https://travis-ci.com/smartshark/mynbou.svg?branch=master)](https://travis-ci.com/smartshark/mynbou)
[![Documentation](https://img.shields.io/badge/docs-latest-brightgreen.svg)](https://smartshark.github.io/mynbou/)

Defect prediction dataset extraction for SmartSHARK.

Included are:
 - Size and complexity metrics, e.g., logical lines of code and cyclomatic complexity.
 - Change metrics, e.g., \#revisions, \#authors, code churn and also age of the files.
 - Automated Static Analysis results via PMD.
 - Post release defects via issues from the issue tracking system linked to commits and then blamed to see if the inducing change happened before the release.

The basic operation is this:
 - change metrics are collected for up to 6 months before the release
 - every post release bug-fix is considered as a candidate, if it has inducing commits only before the release it is included as post-release defect
 - the release itself is used for size, complexity and PMD data
 - the collected data is then harmonized and written to disk

## Install

### via PIP
```bash
pip install https://github.com/smartshark/mynbou/zipball/master
```

### via setup.py
```bash
python setup.py install
```

## Run Tests

To run the tests mongomock is required for integration tests, it also requires a patch to support $addFields aggregation pipeline with missing keys.

```bash
pip install git+https://github.com/atrautsch/mongomock.git@\$addFields
python setup.py test
```

## Execution for SmartSHARK

Mynbou needs only access to the MongoDB, project name and the URL of the repository from which the dataset should be extracted. As we try to incooperate most features mynbou requires that vcsSHARK, mecoSHARK, changeSHARK, coastSHARK, refSHARK, issueSHARK, labelSHARK, linkSHARK and inducingSHARK have already been executed.
The --save-to-mongo option enables the upload of the results back to the MongoDB.

Example execution:

```bash
python smartshark_plugin.py -U $DBUSER -P $DBPASS -DB $DBNAME -u $REPOSITORY_GIT_URI -a $AUTHENTICATION_DB --project-name $PROJECT --release-name $DATASET-1.2 --release-commit $REVISION_HASH --log-level INFO --save-to-mongo
```
