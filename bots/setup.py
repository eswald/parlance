#!/bin/env python
r'''Parang setup script
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

# Class name => module
bots = {
    "BlabberBot": "blabberbot",
    "ComboBot": "combobot",
    "DumbBot": "dumbbot",
    "EvilBot": "evilbot",
    "Neurotic": "neurotic",
    "PeaceBot": "peacebot",
    "Project20M": "project20m",
    "TeddyBot": "teddybot",
}

setup(
    # Provided items
    name = "Parang",
    version = "1.4.1",
    packages = ["parang"],
    entry_points = {
        "console_scripts": [
            "%s = parang.%s:run" % (bot.lower(), bots[bot]) for bot in bots
        ] + [
            "chatty = parang.chatty:run",
        ],
        "gui_scripts": [
        ],
        "parlance.bots": [
            "%s = parang.%s:%s" % (bot, bots[bot], bot) for bot in bots
        ],
    },
    
    # Project metadata
    author = "Eric Wald",
    author_email = "breadman@users.sourceforge.net",
    description = "A set of clients for the Parlance Diplomacy Framework.",
    long_description = readme,
    license = "Non-commercial",
    keywords = "daide diplomacy board game server",
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
    test_suite = "parang.testing",
    install_requires = ["Parlance==1.4.1"],
    package_data = {
        "parang": ["maps/*.tty"],
    },
)
