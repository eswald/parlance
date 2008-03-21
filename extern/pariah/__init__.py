r'''Pariah integration layer for the Parlance Diplomacy framework
    Copyright (C) 2003-2008  Eric Wald
    
    This package helps the Parlance framework interact with external programs,
    allowing it to test their capabilities or start them as bots.
    
    This software may be reused for non-commercial purposes without charge,
    and without notifying the authors.  Use of any part of this software for
    commercial purposes without permission from the authors is prohibited.
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

