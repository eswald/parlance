r'''Parlance Diplomacy framework
    Copyright (C) 2004-2009  Eric Wald
    
    This package is a framework for playing the Diplomacy board game over
    a network, using the client-server protocol and message syntax of the
    Diplomacy Artificial-Intelligence Development Environment (DAIDE)
    community.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

def __version__():
    r'''Tries to get a version number automatically, using setuptools.
        Defined first as a function to avoid leaking imported names.
    '''#'''
    
    try:
        from pkg_resources import get_distribution
        dist = get_distribution(__name__)
    except:
        version = None
    else: version = 'v' + dist.version
    return version
__version__ = __version__()

