r'''Parlance test cases
    Copyright (C) 2004-2009  Eric Wald
    
    This package tests Parlance functionality.  The tests are by no means
    complete, but offer some confidence in the framework.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

import unittest

from parlance.fallbacks import wraps
from parlance.gameboard import Variant

def todo(test):
    '''Makes a test always fail, with an appropriate note.'''
    # Todo: Skip if possible, instead of failing.
    @wraps(test)
    def wrapper(self):
        self.fail("Unwritten test")
    return wrapper

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
    @wraps(test_function)
    def test_wrapper(test_case):
        try: test_function(test_case)
        except test_case.failureException: pass
        else: test_case.fail('Test unexpectedly passed')
    return test_wrapper

def failing(exception):
    ''' Marks a test as throwing an exception, notifying the user otherwise.
        >>> class DummyTestCase:
        ...     failureException = AssertionError
        ...     def fail(self, line=None):
        ...         raise self.failureException(line or 'Test case failed!')
        ...     @failing(ValueError)
        ...     def test_failure(self):
        ...         self.fail()
        ...     @failing(ValueError)
        ...     def test_passing(self):
        ...         pass
        ...     @failing(ValueError)
        ...     def test_expected(self):
        ...         raise ValueError('This error should be silenced.')
        ...     @failing(ValueError)
        ...     def test_error(self):
        ...         raise UserWarning('Other errors propogate through.')
        ...
        >>> d = DummyTestCase()
        >>> d.test_failure()
        Traceback (most recent call last):
            ...
        AssertionError: Test case failed!
        >>> d.test_passing()
        Traceback (most recent call last):
            ...
        AssertionError: Test unexpectedly passed
        >>> d.test_expected()
        >>> d.test_error()
        Traceback (most recent call last):
            ...
        UserWarning: Other errors propogate through.
    '''#'''
    def decorator(test_function):
        @wraps(test_function)
        def test_wrapper(test_case):
            try: test_function(test_case)
            except exception: pass
            else: test_case.fail('Test unexpectedly passed')
        return test_wrapper
    return decorator

def load_variant(information):
    variant = Variant("testing")
    variant.parse(line.strip() for line in information.splitlines())
    return variant

class TestCase(unittest.TestCase):
    '''Extended test case, with functions I always end up using.'''
    def assertContains(self, container, item):
        if item not in container:
            raise self.failureException, '%s not in %s' % (item, container)
