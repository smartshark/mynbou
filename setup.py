#!/usr/bin/env python

import sys

from setuptools import setup, find_packages

if not sys.version_info[0] == 3:
    print('only python3 supported!')
    sys.exit(1)

setup(
    name='mynbou',
    version='0.0.2',
    description='Extraction of defect prediction datasets for SmartSHARK.',
    install_requires=['networkx>=2.2', 'pycoshark>=1.2.6', 'python-dateutil>=2.8.0', 'python-Levenshtein>=0.12.0'],
    author='atrautsch',
    author_email='alexander.trautsch@cs.uni-goettingen.de',
    url='https://github.com/smartshark/mynbou',
    download_url='https://github.com/smartshark/mynbou/zipball/master',
    test_suite='tests',
    packages=find_packages(),
    zip_safe=False,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache2.0 License",
        "Operating System :: POSIX :: Linux",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
