#!/bin/env python
r'''Parlance setup script
    Copyright (C) 2008  Eric Wald
    
    This distribution script uses setuptools, by Phillip J. Eby.
    To use it, enter "python setup.py install" at a command line.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

from ez_setup import use_setuptools
use_setuptools()

from setuptools import setup

setup(
    name = "Parlance",
    version = "1.4.0",
    packages = ["parlance"],
    
    # Project metadata
    author = "Eric Wald",
    author_email = "breadman@users.sourceforge.net",
    description = "A framework for playing the Diplomacy board game over a network.",
    license = "Artistic License 2.0",
    keywords = "daide diplomacy board game server",
    url = "https://sourceforge.net/projects/parlance/",
    
    # Installation options
    zip_safe = True,
    test_suite = "test",
    entry_points = {
        "console_scripts": [
            "parlance-server = parlance.server:run",
            "parlance-holdbot = parlance.player:run",
            "parlance-chatty = parlance.chatty:run",
            "parlance-config = parlance.config:run",
            "parlance-raw-client = parlance.main:run",
            "parlance-raw-server = parlance.network:run",
        ],
        "gui_scripts": [
        ],
    },
    
    package_data = {
        "parlance": ["data/*.html"],
    },
)
