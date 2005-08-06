'''	Functions and classes of general applicability,
	Taken from Peter Norvig's Infrequently Answered Questions,
	at http://www.norvig.com/python-iaq.html
'''#'''

def printf(format, *args): print str(format) % args

def Dict(**kwargs):
	'''	Composes a dictionary with identifiers as keys.
		The only benefit is not having to quote your strings.
		Note: Obsolete in Python 2.3; use dict() instead.
		
		>>> Dict(a=1, b=2, c=3, dee=4)
		{'a': 1, 'b': 2, 'c': 3, 'dee': 4}
	'''#'''
	return kwargs

class Struct:
	def __init__(self, **entries): self.__dict__.update(entries)
	def __repr__(self):
		args = ['%s=%s' % (k, repr(v)) for (k,v) in vars(self).items()]
		return 'Struct(%s)' % ', '.join(args)

def update(item, **entries):
	'''	Generic dictionary/object updating routine.
	'''#'''
	if hasattr(item, 'update'): item.update(entries)
	else: item.__dict__.update(entries)

class DefaultDict(dict):
	'''	Shortcut for a self-initializing dictionary;
		for example, to keep counts of something.
		
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
		import copy
		if key in self: return self.get(key)
		return self.setdefault(key, copy.deepcopy(self.default))

def abstract():
	'''	Marks a method as abstract;
		something that must be implemented in a subclass.
		It's probably better to just raise NotImplementedError, though.
		
		>>> class MyAbstractClass:
		... 	def method1(self): abstract()
		... 
		>>> class MyClass(MyAbstractClass): pass
		... 
		>>> MyClass().method1()
		Traceback (most recent call last):
		    ...
		NotImplementedError: method1 must be implemented in subclass
	'''#'''
	import inspect
	caller = inspect.getouterframes(inspect.currentframe())[1][3]
	raise NotImplementedError(caller + ' must be implemented in subclass')

class Enum:
	'''	Create an enumerated type, then add var/value pairs to it.
		The constructor and the method .ints(names) take a list of variable names,
		and assign them consecutive integers as values.    The method .strs(names)
		assigns each variable name to itself (that is variable 'v' has value 'v').
		The method .vals(a=99, b=200) allows you to assign any value to variables.
		A 'list of variable names' can also be a string, which will be .split().
		The method .end() returns one more than the maximum int value.
		
		>>> opcodes = Enum("add sub load store").vals(illegal=255)
		>>> opcodes.add
		0
		>>> opcodes.illegal
		255
		>>> opcodes.end()
		256
		>>> dir(opcodes)
		['add', 'illegal', 'load', 'store', 'sub']
		>>> vars(opcodes)
		{'store': 3, 'sub': 1, 'add': 0, 'illegal': 255, 'load': 2}
		>>> vars(opcodes).values()
		[3, 1, 0, 255, 2]
	'''#'''

	def __init__(self, names=[]): self.ints(names)

	def set(self, var, val):
		"""Set var to the value val in the enum."""
		if var in vars(self).keys(): raise AttributeError("duplicate var in enum")
		if val in vars(self).values(): raise ValueError("duplicate value in enum")
		vars(self)[var] = val
		return self

	def strs(self, names):
		"""Set each of the names to itself (as a string) in the enum."""
		for var in self._parse(names): self.set(var, var)
		return self

	def ints(self, names):
		"""Set each of the names to the next highest int in the enum."""
		for var in self._parse(names): self.set(var, self.end())
		return self

	def vals(self, **entries):
		"""Set each of var=val pairs in the enum."""
		for (var, val) in entries.items(): self.set(var, val)
		return self

	def end(self):
		"""One more than the largest int value in the enum, or 0 if none."""
		try: return max([x for x in vars(self).values() if type(x)==type(0)]) + 1
		except ValueError: return 0

	def _parse(self, names):
		### If names is a string, parse it as a list of names.
		if type(names) == type(""): return names.split()
		else: return names

class Memoize:
	'''	Calls the function, caching the results for future use.
		Can be used to implement a cached object factory, as well.
	'''#'''
	def __init__(self, fn):
		self.cache = {}
		self.fn = fn
	def __call__(self, *args):
		if self.cache.has_key(args):
			return self.cache[args]
		else:
			result = self.cache[args] = self.fn(*args)
			return result

class Prompt:
    "Create a prompt that stores results (that is, _) in the array h."
    def __init__(self, str='h[%d] >>> '):
        self.str = str;
		#h = [None]

    def __str__(self):
        try:
            if _ not in [h[-1], None, h]: h.append(_);
        except NameError:
            pass
        return self.str % len(h);

    def __radd__(self, other):
        return str(other) + str(self)
# Try this in ~/.python:
#import sys
#h = [None]
#if os.environ.get('TERM') in [ 'xterm', 'vt100' ]:
#    sys.ps1 = Prompt('\001\033[0:1;31m\002h[%d] >>> \001\033[0m\002')
#else:
#    sys.ps1 = Prompt()
#sys.ps2 = ''


def _test():
	import doctest, functions
	return doctest.testmod(functions)
if __name__ == "__main__": _test()

# vim: ts=4 sw=4 noet
