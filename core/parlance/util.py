r'''Parlance general utility definitions
    Copyright (C) 2004-2009  Eric Wald
    
    This module includes generic definitions used by the Parlance package.
    Several of them were adapted from previous works.  New items may be added
    at any time, so "from util import *" is discouraged.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

from itertools import chain
from random import randrange
from time import gmtime

import parlance


def rindex(series, value):
    ''' Finds the last index of value in series.
        >>> rindex([3,4,5,6,5,4,3], 4)
        5
        >>> rindex([3,4,5,6,5,4,3], 2)
        Traceback (most recent call last):
            ...
        ValueError: list.index(x): x not in list
    '''#'''
    return len(series) - series[::-1].index(value) - 1

def s(count):
    if count == 1: return ''
    else: return 's'

def expand_list(items, conjunction='and'):
    ''' Expands a list into a string suitable for a sentence.
        Uses commas if the list contains at least three items.
        
        >>> nums = ['one', 'two', 'three', 'four']
        >>> while nums:
        ...     nothing = nums.pop()
        ...     print expand_list(nums)
        ... 
        one, two, and three
        one and two
        one
        nothing
    '''#'''
    items = list(items)
    if items:
        result = str(items.pop(0))
        if len(items) > 1: result += ','
        while len(items) > 1: result += ' %s,' % (items.pop(0),)
        if items: result += ' %s %s' % (conjunction, items[0])
        return result
    else: return 'nothing'

class autosuper(type):
    ''' Allows instances of instances of this class to use self.__super
        to cooperatively call overridden methods.
        Taken from Guido's "Unifying types and classes in Python 2.2"
    '''#'''
    def __init__(cls, name, bases, dict):
        # Raise an exception if any base class has the same name.
        assert name not in [base.__name__ for base in bases]
        super(autosuper, cls).__init__(name, bases, dict)
        setattr(cls, "_%s__super" % name, super(cls))

class Comparable(object):
    ''' Defines new-style operators in terms of the old.
        >>> class TestComparable(Comparable):
        ...     def __init__(self, value):
        ...         self.value = value
        ...     def __cmp__(self, other):
        ...         return cmp(self.value, other.value)
        ...     def __repr__(self):
        ...         return 'TC(%r)' % self.value
        ... 
        >>> a = TestComparable(1)
        >>> b = TestComparable(3)
        >>> c = TestComparable(2)
        >>> a > c
        False
        >>> d = [a,b,c]; d.sort(); print d
        [TC(1), TC(2), TC(3)]
    '''#'''
    def __eq__(self, other): return not self.__cmp__(other)
    def __ne__(self, other): return not self.__eq__(other)
    def __gt__(self, other): return self.__cmp__(other) > 0
    def __lt__(self, other): return self.__cmp__(other) < 0
    def __ge__(self, other): return not self.__lt__(other)
    def __le__(self, other): return not self.__gt__(other)
    def __cmp__(self, other): return NotImplemented

class Immutable(object):
    ''' Tries to make objects basically immutable.
        This implementation even restricts new elements on the class itself.
    '''#'''
    class __metaclass__(type):
        def __setattr__(cls, name, value):
            if hasattr(cls, name):
                #type.__setattr__(self, name, value)
                raise AttributeError("'%s' class attribute '%s' is read-only" %
                        (cls.__name__, name))
            else:
                raise AttributeError("'%s' class has no attribute '%s'" %
                        (cls.__name__, name))
    
    def __setattr__(self, name, value):
        def slots(klass):
            result = getattr(klass, '__slots__', ())
            if isinstance(result, str): result = (result,)
            #else: result = tuple(result)
            return result
        cls = self.__class__
        if hasattr(self, name):
            raise AttributeError("'%s' object attribute '%s' is read-only" %
                    (cls.__name__, name))
        elif name in chain(*(slots(klass) for klass in cls.__mro__)):
            super(Immutable, self).__setattr__(name, value)
        else:
            raise AttributeError("'%s' object has no attribute '%s'" %
                    (cls.__name__, name))

# This used to be a custom class, but Python has a builtin that works.
Infinity = float("inf")

class settable_property(object):
    def __init__(self, fget): self.fget = fget
    def __get__(self, obj, type): return self.fget(obj)

def version_string(extra=None):
    ''' Compute a version string for the NME message.
        The version string starts with 'Parlance',
        and ends with the Parlance version or commit id.
        If extra is given, it is stuffed in between.
    '''#'''
    items = ['Parlance', extra, parlance.__version__]
    return str.join(' ', filter(None, items))

def num2name(number):
    ''' Converts an integer into an English phrase.
        >>> num2name(2000)
        'two thousand'
        >>> num2name(1900)
        'nineteen hundred'
        >>> num2name(816)
        'eight hundred sixteen'
        >>> num2name(1)
        'one'
        >>> num2name(42)
        'forty-two'
    '''#'''
    
    # Large numbers
    if number == 1000: return 'a thousand'
    if 1000 < number < 1000000 and not number % 1000:
        return num2name(number // 1000) + ' thousand'
    if number == 100: return 'a hundred'
    if 100 < number < 10000 and not number % 100:
        return num2name(number // 100) + ' hundred'
    if number > 1000: return str(number)
    
    # Tables
    names = {
        0: None,
        1: 'one',
        2: 'two',
        3: 'three',
        4: 'four',
        5: 'five',
        6: 'six',
        7: 'seven',
        8: 'eight',
        9: 'nine',
        10: 'ten',
        11: 'eleven',
        12: 'twelve',
        13: 'thirteen',
        14: 'forteen',
        15: 'fifteen',
        16: 'sixteen',
        17: 'seventeen',
        18: 'eighteen',
        19: 'nineteen',
        20: 'twenty',
        30: 'thirty',
        40: 'forty',
        50: 'fifty',
        60: 'sixty',
        70: 'seventy',
        80: 'eighty',
        90: 'ninety',
    }
    
    # Small numbers
    hundreds = tens = None
    if number >= 100:
        hundreds = names[number // 100] + ' hundred'
        number %= 100
    if number >= 20:
        tens = names[number - (number % 10)]
        number %= 10
    result = names[number]
    if tens: result = result and (tens + '-' + result) or tens
    if hundreds: result = result and (hundreds + ' ' + result) or hundreds
    return result or 'zero'

def instances(number, name, article=True):
    if article and number == 1:
        if name[0] in "aeiouAEIOU": prefix = 'an '
        else: prefix = 'a '
    elif number > 1: prefix = '%s instances of ' % num2name(number)
    else: prefix = ''
    return prefix + name

def random_cycle(start, stop, step=1):
    r'''Iterate through each value, starting at a random point.
        Stops when all values have been returned.
        
        >>> from parlance.fallbacks import defaultdict
        >>> print sorted(random_cycle(1, 6))
        [1, 2, 3, 4, 5]
        
        # Accepts an optional step value
        >>> print sorted(random_cycle(1, 8, 2))
        [1, 3, 5, 7]
        
        # Runs through the sequence in order
        >>> prev = None
        >>> counts = defaultdict(int)
        >>> for val in random_cycle(15, 32):
        ...     if prev is not None:
        ...         counts[val - prev] += 1
        ...     prev = val
        ...
        >>> print sorted(counts.items())
        [(-16, 1), (1, 15)]
        
        >>> vals = set()
        >>> for iteration in range(10):
        ...     val = random_cycle(0, 10).next()
        ...     vals.add(val)
        ...
        >>> len(vals) > 1
        True
    '''#"""#'''
    first = randrange(start, stop, step)
    for val in xrange(first, stop, step):
        yield val
    for val in xrange(start, first, step):
        yield val

def static(**kwargs):
    r'''Initializes static variables of a function.
        Such variables can then be accessed as attributes of
        the function itself, assuming you know how to find it.
        Warning: Don't use attributes set by Python itself.
        
        >>> @static(compound='')
        ... def f(s):
        ...     f.compound += s
        ...     return f.compound
        ...
        >>> f('a')
        'a'
        >>> f('b')
        'ab'
    '''#"""#'''
    def decorator(func):
        for key in kwargs:
            setattr(func, key, kwargs[key])
        return func
    return decorator

@static(base=None, appendix=0)
def timestamp(seconds=None):
    ''' Creates a game name from the current time.
        This implementation can handle up to fifty games per second;
        beyond that, it starts creating nine-character names.
        The names will sort chronologically in ASCII-based systems,
        but wrap every forty years.
        
        Vowels have been removed to prevent production of real words.
        This also reduces the chance of conflict with human-given names.
        All names will start with a letter and end in two numbers;
        the other five characters can be letters or numbers.
        
        >>> from time import mktime, timezone, altzone
        >>> def mkgmtime(when):
        ...     seconds = mktime(when)
        ...     seconds -= [timezone, altzone][when[8]]
        ...     return seconds
        ... 
        >>> when = [2008, 2, 23, 20, 23, 7, 5, 54, 0]
        >>> seconds = mkgmtime(when)
        >>> print timestamp(seconds)
        G2QNC300
        >>> print timestamp(seconds)
        G2QNC301
        >>> when[0] -= 40
        >>> print timestamp(mkgmtime(when))
        G2QNC302
        >>> when[0] += 20
        >>> print timestamp(mkgmtime(when))
        S2QNC300
        >>> when[0] += 1
        >>> print timestamp(mkgmtime(when))
        SGQNC300
        >>> when[0] += 10
        >>> print timestamp(mkgmtime(when))
        YGQNC300
        >>> when[5] += 1
        >>> print timestamp(mkgmtime(when))
        YGQNC400
        >>> when[5] += 1
        >>> print timestamp(mkgmtime(when))
        YGQNC401
    '''#'''
    chars = "0123456789BCDFGHJKLMNPQRSTVWXYZ"
    now = gmtime(seconds)
    year = ((now[0] // 2) % 20) + 10    # 10 - 29
    month = now[1] + (now[0] % 2) * 12  #  1 - 24
    day = now[2] - 1                    #  0 - 30
    hour = now[3]                       #  0 - 23
    minute = now[4] // 2                #  0 - 29
    second = now[5] // 2                #  0 - 29 (or perhaps 30)
    result = (chars[year] + chars[month] + chars[day] +
            chars[hour] + chars[minute] + chars[second])
    if result == timestamp.base:
        timestamp.appendix += 1
    else:
        timestamp.base = result
        timestamp.appendix = 0
    return '%s%02d' % (result, timestamp.appendix)

def bit(value):
    r'''Verifies that the value is an integer with a single bit set.
        Meant for use as a configuration option parser.
        
        >>> bit(0x40)
        64
        >>> bit("0x10")
        16
        >>> bit(True)
        1
        >>> bit(0)
        Traceback (most recent call last):
            ...
        ValueError: Invalid bit value 0
        >>> bit("0x11")
        Traceback (most recent call last):
            ...
        ValueError: Invalid bit value '0x11'
        >>> bit("on")
        Traceback (most recent call last):
            ...
        ValueError: invalid literal for int() with base 0: 'on'
    '''#"""#'''
    try:
        n = int(value)
    except ValueError:
        # Possibly a hexadecimal string
        # If the value is really wrong, this will fail again.
        n = int(value, 0)
    
    if (n & (n - 1)) or not n:
        # There's more than one set bit in the number
        raise ValueError("Invalid bit value %r" % (value,))
    
    return n

