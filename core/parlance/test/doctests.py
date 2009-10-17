r'''Docstring test cases for Parlance modules
    Copyright (C) 2004-2009  Eric Wald
    
    This module runs docstring tests in selected Parlance modules.
    It should import them into the unittest framework for setuptools.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

import doctest
import sys

from parlance import fallbacks
from parlance import gameboard
from parlance import language
from parlance import orders
from parlance import test
from parlance import util
from parlance import validation
from parlance import xtended

# List of modules to test
modules = [
    fallbacks,
    gameboard,
    language,
    orders,
    test,
    util,
    validation,
]

def create_extension():
    extension = dict((name, getattr(xtended, name))
        for name in xtended.__all__)
    extension.update(language.protocol.base_rep)
    return extension

def configure():
    # Configure basic options assumed by docstrings
    opts = language.protocol.base_rep.options
    opts.squeeze_parens = False
    opts.output_escape = '"'
    opts.quot_char = '"'

def _test():
    extension = create_extension()
    verbose = "-v" in sys.argv
    
    for mod in modules:
        print 'Testing', mod.__name__
        configure()
        
        globs = mod.__dict__
        globs.update(extension)
        doctest.testmod(mod, verbose=verbose, report=0, globs=globs)
    doctest.master.summarize()

def doctest_runner(case):
    def wrapper():
        configure()
        return case.runTest()
    
    # str(case) would be more robust, but this looks better.
    wrapper.__name__ = "test " + case._dt_test.name
    return wrapper

def install_suites():
    extension = create_extension()
    this = sys.modules[__name__]
    for module in modules:
        suite = doctest.DocTestSuite(module, extraglobs=extension)
        for case in suite:
            runner = doctest_runner(case)
            setattr(this, runner.__name__, runner)

if __name__ == "__main__":
    _test()
else:
    install_suites()
