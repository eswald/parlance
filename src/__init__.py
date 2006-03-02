#!/usr/bin/env python
''' PyDip - A Python framework for DAIDE
    (Diplomacy Artificial Intelligence Development Environment)
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
    
    Contains modules for Diplomacy client and server programs:
        gameboard   -- Classes for game elements: Map, Unit, Province, Power.
        config      -- Loads constants from various configuration files.
        dumbbot     -- A client ported from David Norman's DumbBot code
        human       -- Clients that interact with real people.
        judge       -- Move parser and adjudicator.
        language    -- Classes to parse and use the modified DPP language.
        main        -- The program core.  Instantiates and controls components.
        network     -- Classes to exchange information between client and server.
        player      -- Basic clients.
        server      -- The main server classes.
        translation -- The function to translate strings into Messages.
        validation  -- The function to validate incoming Messages.
'''#'''

# Important initialization
import config

# List of available modules
__all__ = [
    'gameboard',
    'config',
    'dumbbot',
    'human',
    'judge',
    'language',
    'main',
    'network',
    'player',
    'server',
    'translation',
    'validation',
]

def _test():
    import doctest, sys
    
    import gameboard
    import dumbbot
    import human
    import judge
    import language
    import main
    import network
    import player
    import server
    import translation
    import validation
    
    # List of modules to test
    modules = [
        gameboard,
        config,
        dumbbot,
        human,
        judge,
        language,
        main,
        network,
        player,
        server,
        translation,
        validation,
    ]
    
    extension = config.extend_globals({})
    verbose = "-v" in sys.argv
    for mod in modules:
        print 'Testing', mod.__name__
        globs = mod.__dict__
        globs.update(extension)
        doctest.testmod(mod, verbose=verbose, report=0, globs=globs)
    doctest.master.summarize()

if __name__ == "__main__": _test()
