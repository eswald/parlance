#!/bin/env python
from ez_setup import use_setuptools
use_setuptools()

from setuptools import setup

setup(
    name = "Parlance",
    version = "1.4.0.dev",
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
            "parlance-server = parlance.main:run_server",
        ],
        "gui_scripts": [
        ],
    },
)
