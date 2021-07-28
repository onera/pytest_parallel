#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import codecs
import setuptools


def read(fname):
    file_path = os.path.join(os.path.dirname(__file__), fname)
    return codecs.open(file_path, encoding='utf-8').read()


setuptools.setup(
    name='pytest-mpi-check',
    version='0.1.0',
    author='Bruno Maugars',
    author_email='bruno.maugars@onera.fr',
    maintainer='Bruno Maugars',
    maintainer_email='bruno.maugars@onera.fr',
    license='Mozilla Public License 2.0',
    url='https://github.com/maugarsb/pytest-mpi-check',
    description='Plugin to manage test in distributed way with MPI Standard',
    long_description=read('README.rst'),
    packages=setuptools.find_packages(),
    python_requires='>=3.5',
    install_requires=['pytest>=3.5.0'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Framework :: Pytest',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Testing',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: Implementation :: CPython',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)',
    ],
    entry_points={
        'pytest11': [
            'mpi-check = pytest_mpi_check',
        ],
    },
)
