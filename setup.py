"""Setup script for ton-ts4"""

import os.path
from setuptools import find_packages, setup

from tonos_ts4.ts4 import __version__ as ts4_version

HERE = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(HERE, 'README_PYPI.md')) as fh:
    README = fh.read()

NAME = 'tonos_ts4'
VERSION = ts4_version
AUTHOR = "TON Labs"
EMAIL = 'info@tonlabs.io'
LICENSE = "Apache"

setup(
    name=NAME,
    version=VERSION,
    description='TestSuite4 is a framework designed to simplify development and testing of TON Contracts',
    long_description=README,
    long_description_content_type='text/markdown',
    url='https://github.com/tonlabs/TestSuite4',
    author=AUTHOR,
    author_email=EMAIL,
    license=LICENSE,
    classifiers=[
        'Environment :: Console',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Testing',
    ],
    keywords='freeton ton tvm blockchain testing tonlabs ts4 testsuite',
    packages=['tonos_ts4'],
    package_data={'tonos_ts4': [
        'darwin/linker_lib.so',
        'linux/linker_lib.so',
        'win32/linker_lib.pyd',
    ]},
    include_package_data=True,
    install_requires=[],
    python_requires='>=3.6, <=3.10',
    #zip_safe=False,
)
