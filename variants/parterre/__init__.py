r'''Parterre Diplomacy variants
    Copyright (C) 1990-2009  Eric Wald, David Norman, and many others
    
    Parterre is a set of variant maps for the Diplomacy board game,
    formatted for use by the Parlance framework.
    
    This package may be reused for non-commercial purposes without charge,
    and without notifying the authors.  Use of any part of this package for
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

