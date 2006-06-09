#!/usr/bin/env python
''' PyDip - A Python framework for DAIDE
    (Diplomacy Artificial Intelligence Development Environment)
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
    
    Contains modules for Diplomacy client and server programs:
        config      -- Loads constants from various configuration files.
        dumbbot     -- A client ported from David Norman's DumbBot code
        gameboard   -- Classes for game elements: Map, Unit, Province, Power.
        judge       -- Move parser and adjudicator.
        language    -- Classes to parse and use the modified DPP language.
        main        -- The program core.  Instantiates and controls components.
        network     -- Classes to exchange information between client and server.
        player      -- Basic clients.
        server      -- The main server classes.
        tokens      -- Tokens of the core DPP language.
        validation  -- The function to validate incoming Messages.
    
    When run directly as a script, this module starts the server.
'''#'''

# List of available modules
__all__ = [
    'config',
    'dumbbot',
    'evilbot',
    'functions',
    'gameboard',
    'judge',
    'language',
    'main',
    'network',
    'orders',
    'player',
    'server',
    'tokens',
    'validation',
    'xtended',
]

if __name__ == "__main__":
    import server
    server.run()
