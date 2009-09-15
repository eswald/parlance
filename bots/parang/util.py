r'''Parang general utility definitions
    Copyright (C) 2004-2009  Eric Wald
    
    This module includes generic definitions used by the Parang package.
    New items may be added at any time.
    
    This software may be reused for non-commercial purposes without charge,
    and without notifying the authors.  Use of any part of this software for
    commercial purposes without permission from the authors is prohibited.
'''#'''

from parlance.util import static

def sublists(series):
    ''' Returns a list of sublists of the series.
        The series itself and the empty list are included.
        Sublists are determined by index, not value;
        if the series contains duplicates, so will the result.
        
        >>> nums = [1, 2, 3]
        >>> subs = sublists(nums)
        >>> subs.sort()
        >>> print subs
        [[], [1], [1, 2], [1, 2, 3], [1, 3], [2], [2, 3], [3]]
        
        >>> nums = [1, 3, 3]
        >>> subs = sublists(nums)
        >>> subs.sort()
        >>> print subs
        [[], [1], [1, 3], [1, 3], [1, 3, 3], [3], [3], [3, 3]]
    '''#'''
    subs = [[]]
    for tail in series: subs += [head + [tail] for head in subs]
    return subs

@static(data=None)
def cache(key, factory, *args, **kwargs):
    r'''Simple cache system.
        If the key exists in the cache, its value is returned.
        Otherwise, the factory function is called with any supplied arguments,
        and its value is stored in the cache as the new value.
        Ideally, the factory should be idempotent;
        cache items may be stored indefinitely, or discarded at any time.
        
        >>> def f(value):
        ...     print "Storing " + repr(value)
        ...     return value
        ...
        >>> cache('a', f, 'b')
        Storing 'b'
        'b'
        >>> cache('a', f, 'b')
        'b'
        >>> cache('b', f, value='c')
        Storing 'c'
        'c'
        
        # Cleanup to make the tests work next time; not part of the API
        >>> del cache.data['a']
        >>> del cache.data['b']
    '''#"""#'''
    
    # Todo: "expires" keyword argument?
    # Todo: Make the filename configurable.
    # Todo: Clean up the complaints from Python 2.5.2
    
    if cache.data is None:
        import shelve
        cache.data = shelve.open("datastore")
    
    if key in cache.data:
        value = cache.data[key]
    else:
        value = factory(*args, **kwargs)
        cache.data[key] = value
        cache.data.sync()
    return value
