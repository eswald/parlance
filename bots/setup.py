#!/bin/env python
r'''Parang setup script
    Copyright (C) 2008-2009  Eric Wald
    
    This distribution script uses setuptools, by Phillip J. Eby.
    To use it, enter "python setup.py install" at a command line.
    
    This software may be reused for non-commercial purposes without charge,
    and without notifying the authors.  Use of any part of this software for
    commercial purposes without permission from the authors is prohibited.
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

# Class name => module
bots = {
    "BlabberBot": "blabberbot",
    "ComboBot": "combobot",
    "DumbBot": "dumbbot",
    "EvilBot": "evilbot",
    "PeaceBot": "peacebot",
    "Project20M": "project20m",
    "TeddyBot": "teddybot",
}

setup(
    # Provided items
    name = "Parang",
    version = __version__,
    packages = ["parang"],
    entry_points = {
        "console_scripts": [
            "%s = parang.%s:%s.main" % (bot.lower(), bots[bot], bot) for bot in bots
        ] + [
            "parang-chatty = parang.chatty:Chatty.main",
            "parang-mapchat = parang.chatty:MapChat.main",
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
    keywords = "daide diplomacy board game AI bots",
    platforms = "Any",
    classifiers = [
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Environment :: Console :: Curses",
        "Environment :: Plugins",
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
    tests_require = [
        "mock >= 0.6.0",
    ],
    #install_requires = ["Parlance == " + __version__],
    package_data = {
        "parang": ["maps/*.tty"],
    },
)
