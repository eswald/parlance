#!/bin/env python
r'''Parterre setup script
    Copyright (C) 2008  Eric Wald
    
    This distribution script uses setuptools, by Phillip J. Eby.
    To use it, enter "python setup.py install" at a command line.
    
    This software may be reused for non-commercial purposes without charge,
    and without notifying the authors.  Use of any part of this software for
    commercial purposes without permission from the authors is prohibited.
'''#'''

try:
    from setuptools import setup
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup

try:
    readme = open('README.txt').read()
except:
    # Todo: Attempt to find the README file.
    readme = None

def variant_list():
    from os import listdir, path
    entries = []
    for filename in listdir(path.join("parterre", "data")):
        name, extension = path.splitext(filename)
        if extension.endswith("cfg"):
            entry_point = "%s = parterre.loader:loader.%s" % (name, name)
            entries.append(entry_point)
    return entries

setup(
    # Provided items
    name = "Parterre",
    version = "1.4.1",
    packages = ["parterre"],
    entry_points = {
        "parlance.variants": variant_list(),
    },
    
    # Project metadata
    author = "Eric Wald",
    author_email = "breadman@users.sourceforge.net",
    description = "A set of variants for the Parlance Diplomacy Framework.",
    long_description = readme,
    license = "Non-commercial",
    keywords = "daide diplomacy board game variants",
    platforms = "Any",
    classifiers = [
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Environment :: Console :: Curses",
        "Environment :: No Input/Output (Daemon)",
        "License :: Free for non-commercial use",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Topic :: Games/Entertainment :: Board Games",
        "Topic :: Games/Entertainment :: Turn Based Strategy",
    ],
    
    # Installation options
    zip_safe = True,
    test_suite = "parterre.testing",
    install_requires = ["Parlance>=1.4.1"],
    package_data = {
        "parterre": ["data/*.cfg"],
    },
)
