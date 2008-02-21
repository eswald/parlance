r'''Parlance Diplomacy framework
    Copyright (C) 2004-2008  Eric Wald
    
    This package is a framework for playing the Diplomacy board game over
    a network, using the client-server protocol and message syntax of the
    Diplomacy Artificial-Intelligence Development Environment (DAIDE)
    community.
    
    When run directly as a script, this module starts the server.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

# List of available modules
__all__ = [
    'chatty',
    'config',
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
