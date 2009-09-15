r'''Parlance backwards-compatibility fallbacks
    Copyright (C) 2004-2009  Eric Wald
    
    Parlance is intended to work with any Python version from 2.4 on.
    This module includes items added to later versions.
    Built-in items are used where available, for speed.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

try:
    from functools import wraps
except ImportError:
    def wraps(function):
        '''Makes a function wrapper look like the function it wraps.'''
        def decorator(wrapped):
            wrapped.__doc__ = function.__doc__
            wrapped.__name__ = function.__name__
            return wrapped
        return decorator

try:
    any = any
except NameError:
    def any(sequence):
        r'''Returns True any item in the sequence is true.
            Short-circuits, if possible.
            
            >>> def print_and_negate(val):
            ...     print val,; return not val
            ...
            >>> any(print_and_negate(x) for x in range(3,-3,-1))
            3 2 1 0
            True
            >>> any([])
            False
        '''#'''
        from itertools import ifilter
        for unused in ifilter(bool, sequence):
            return True
        return False

try:
    all = all
except NameError:
    def all(sequence):
        r'''Returns whether every item in the sequence is true.
            Short-circuits, if possible.
            
            >>> def print_and_return(val):
            ...     print val,; return val
            ...
            >>> all(print_and_return(x) for x in range(3,-3,-1))
            3 2 1 0
            False
            >>> all([])
            True
        '''#'''
        from itertools import ifilterfalse
        for unused in ifilterfalse(bool, sequence):
            return False
        return True

try:
    defaultdict = defaultdict
except NameError:
    class defaultdict(dict):
        r'''Shortcut for a self-initializing dictionary;
            for example, to keep counts of something.
            Designed to emulate the implemenation in Python 2.5
            
            >>> d = defaultdict(lambda: 1)
            >>> d['hello'] += 1
            >>> d
            {'hello': 2}
            >>> d2 = defaultdict(list)
            >>> d2[1].append('hello')
            >>> d2[2].append('world')
            >>> d2[1].append('there')
            >>> d2
            {1: ['hello', 'there'], 2: ['world']}
            >>> d2.has_key(3)
            False
        '''#'''
        __slots__ = ('default_factory',)
        def __init__(self, default_factory=None):
            self.default_factory = default_factory
        def __getitem__(self, key):
            try: result = dict.__getitem__(self, key)
            except KeyError: result = self.__missing__(key)
            return result
        def __missing__(self, key):
            if self.default_factory is None:
                raise KeyError(key)
            else:
                result = self.default_factory()
                self[key] = result
                return result
