''' Functions of general applicability
    
    New functions may be added at any time,
    so "from functions import *" is discouraged.
'''#'''

from os        import linesep
from itertools import ifilter, ifilterfalse

def any(sequence):
    ''' Returns True any item in the sequence is true.
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
    for unused in ifilter(bool, sequence): return True
    return False

def all(sequence):
    ''' Returns whether every item in the sequence is true.
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
    for unused in ifilterfalse(bool, sequence): return False
    return True

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

class Infinity(object):
    def __gt__(self, other): return True
    def __lt__(self, other): return False
    def __ge__(self, other): return True
    def __le__(self, other): return False
    def __str__(self): return 'Infinity'
Infinity = Infinity()

class settable_property(object):
    def __init__(self, fget): self.fget = fget
    def __get__(self, obj, type): return self.fget(obj)

class Verbose_Object(object):
    __metaclass__ = autosuper
    log_file = None
    verbosity = 1
    __files = {}
    def log_debug(self, level, line, *args):
        if level <= self.verbosity:
            line = self.prefix + ': ' + str(line) % args
            if self.log_file:
                try: output = self.__files[self.log_file]
                except KeyError:
                    output = file(self.log_file, 'a')
                    self.__files[self.log_file] = output
                output.write(line + linesep)
            else:
                try: print line
                except IOError: self.verbosity = 0 # Ignore broken pipes
    @settable_property
    def prefix(self): return self.__class__.__name__

def absolute_limit(time_limit):
    ''' Converts a TME message number into a number of seconds.
        Negative message numbers indicate hours; positive, seconds.
    '''#'''
    if time_limit < 0: result = -time_limit * 3600
    else: result = time_limit
    return result
def relative_limit(seconds):
    ''' Converts a number of seconds into a TME message number.
        Negative message numbers indicate hours; positive, seconds.
        Negative times are cropped to zero.
    '''#'''
    from language import Token
    max_int = Token.opts.max_pos_int
    if seconds > max_int: result = -seconds // 3600
    else: result = max(0, seconds)
    if -result > max_int: result = -max_int
    return result

class DefaultDict(dict):
    ''' Shortcut for a self-initializing dictionary;
        for example, to keep counts of something.
        
        Taken from Peter Norvig's Infrequently Answered Questions,
        at http://www.norvig.com/python-iaq.html
        Modified to resemble Maxim Krikun's solution, at
        http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/259173
        
        >>> d = DefaultDict(0)
        >>> d['hello'] += 1
        >>> d
        {'hello': 1}
        >>> d2 = DefaultDict([])
        >>> d2[1].append('hello')
        >>> d2[2].append('world')
        >>> d2[1].append('there')
        >>> d2
        {1: ['hello', 'there'], 2: ['world']}
    '''#'''
    __slots__ = ('default',)
    def __init__(self, default): self.default = default
    def __getitem__(self, key):
        try: result = dict.__getitem__(self, key)
        except KeyError:
            item = self.default
            if callable(item): result = item()
            else:
                import copy
                result = copy.deepcopy(item)
            self[key] = result
        return result

def version_string(revision, extra=None):
    ''' Converts a Subversion revision string into a NME version string.'''
    import config
    if extra: main = extra + ' '
    else: main = ''
    return revision.replace(' $', '').replace('$Revision: ',
            'PyDip %s%s.' % (main, config.__version__))

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

def fails(test_function):
    ''' Marks a test as failing, notifying the user when it succeeds.
        >>> class DummyTestCase:
        ...     failureException = AssertionError
        ...     def fail(self, line=None):
        ...         raise self.failureException(line or 'Test case failed!')
        >>> d = DummyTestCase()
        >>> def test_failure(self):
        ...     self.fail('This test should fail silently.')
        >>> fails(test_failure)(d)
        >>> def test_failure(self):
        ...     pass
        >>> fails(test_failure)(d)
        Traceback (most recent call last):
            ...
        AssertionError: Test unexpectedly passed
        >>> def test_failure(self):
        ...     raise ValueError('Errors propogate through.')
        >>> fails(test_failure)(d)
        Traceback (most recent call last):
            ...
        ValueError: Errors propogate through.
    '''#'''
    def test_wrapper(test_case):
        try: test_function(test_case)
        except test_case.failureException: pass
        else: test_case.fail('Test unexpectedly passed')
    return test_wrapper

def _test():
    import doctest, functions
    return doctest.testmod(functions)
if __name__ == "__main__": _test()
