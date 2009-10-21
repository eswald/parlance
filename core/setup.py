#!/bin/env python
r'''Parlance setup script
    Copyright (C) 2008-2009  Eric Wald
    
    This distribution script uses setuptools, by Phillip J. Eby.
    To use it, enter "python setup.py install" at a command line.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

__version__ = "1.5.0"

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

setup(
    # Provided items
    name = "Parlance",
    version = __version__,
    packages = ["parlance"],
    entry_points = {
        "console_scripts": [
            "parlance-server = parlance.server:Server.main",
            "parlance-holdbot = parlance.player:HoldBot.main",
            "parlance-config = parlance.config:ConfigPrinter.main",
            "parlance-raw-client = parlance.main:RawClient.main",
            "parlance-raw-server = parlance.main:RawServer.main",
        ],
        "gui_scripts": [
        ],
        "parlance.bots": [
            "HoldBot = parlance.player:HoldBot",
        ],
        "parlance.judges": [
            "standard = parlance.judge:Judge",
        ],
        "parlance.variants": [
            "standard = parlance.xtended:standard",
        ],
        "parlance.watchers": [
            "ladder = parlance.watcher:Ladder",
        ],
    },
    
    # Project metadata
    author = "Eric Wald",
    author_email = "breadman@users.sourceforge.net",
    description = "A framework for playing the Diplomacy board game over a network.",
    long_description = readme,
    license = "Artistic License 2.0",
    keywords = "daide diplomacy board game server",
    url = "http://sourceforge.net/projects/parlance/",
    platforms = "Any",
    classifiers = [
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Environment :: No Input/Output (Daemon)",
        "License :: OSI Approved :: Artistic License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Topic :: Games/Entertainment :: Board Games",
        "Topic :: Games/Entertainment :: Turn Based Strategy",
    ],
    
    # Installation options
    zip_safe = True,
    install_requires = [
        "Twisted-Core >= 8.1.0",
        "setuptools >= 0.6c7",
    ],
    test_suite = "parlance.test",
    tests_require = [
        "mock >= 0.6.0",
    ],
    extras_require = {
        'bots': ["Parang == " + __version__],
        'maps': ["Parterre == " + __version__],
    },
    package_data = {
        "parlance": ["data/*.html", "data/*.cfg"],
    },
)
