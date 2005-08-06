'''	Functions of general applicability.
	New functions may be added at any time,
	so "from functions import *" is discouraged.
'''#'''

from os        import linesep
from itertools import ifilter, ifilterfalse

def any(sequence, predicate=bool):
	'''	Returns True if the predicate passes for any item in the list.
		Short-circuits, if possible.
		>>> def print_and_negate(val):
		... 	print val,; return not val
		...
		>>> any(range(3,-3,-1), print_and_negate)
		3 2 1 0
		True
	'''#'''
	for unused in ifilter(predicate, sequence): return True
	return False

def all(sequence, predicate=bool):
	'''	Returns whether the predicate passes for every item in the list.
		Short-circuits, if possible.
		>>> def print_and_return(val):
		... 	print val,; return val
		...
		>>> all(range(3,-3,-1), print_and_return)
		3 2 1 0
		False
	'''#'''
	for unused in ifilterfalse(predicate, sequence): return False
	return True

def rindex(series, value):
	'''	Finds the last index of value in series.
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
	'''	Expands a list into a string suitable for a sentence.
		Uses commas if the list contains at least three items.
		
		>>> nums = ['one', 'two', 'three', 'four']
		>>> while nums:
		... 	nothing = nums.pop()
		... 	print expand_list(nums)
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
	'''	Allows instances of instances of this class to use self.__super
		to cooperatively call overridden methods.
		Taken from Guido's "Unifying types and classes in Python 2.2"
	'''#'''
	def __init__(cls, name, bases, dict):
		# Raise an exception if any base class has the same name.
		assert name not in [base.__name__ for base in bases]
		super(autosuper, cls).__init__(name, bases, dict)
		setattr(cls, "_%s__super" % name, super(cls))

def sublists(series):
	'''	Returns a list of sublists of the series.
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
	'''	Defines new-style operators in terms of the old.
		>>> class TestComparable(Comparable):
		... 	def __init__(self, value):
		... 		self.value = value
		... 	def __cmp__(self, other):
		... 		return cmp(self.value, other.value)
		... 	def __repr__(self):
		... 		return 'TC(%r)' % self.value
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

class Verbose_Object(object):
	__metaclass__ = autosuper
	log_file = None
	verbosity = 0
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
			else: print line
	def prefix(self): return self.__class__.__name__
	prefix = property(fget=prefix)

def _test():
	import doctest, functions
	return doctest.testmod(functions)
if __name__ == "__main__": _test()

# vim: ts=4 sw=4 noet
