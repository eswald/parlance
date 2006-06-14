''' PyDip docstring testing
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
    
    When run, this module runs docstring tests in other modules.
'''#'''

def _test():
    import doctest
    import sys
    
    import functions
    import gameboard
    import language
    import orders
    import validation
    import xtended
    
    # List of modules to test
    modules = [
        functions,
        gameboard,
        language,
        orders,
        validation,
    ]
    
    extension = dict((name, getattr(xtended, name)) for name in xtended.__all__)
    extension.update(language.protocol.base_rep)
    verbose = "-v" in sys.argv
    
    for mod in modules:
        print 'Testing', mod.__name__
        # Configure basic options assumed by docstrings
        opts = language.protocol.base_rep.options
        opts.squeeze_parens = False
        opts.output_escape = '"'
        opts.quot_char = '"'
        
        globs = mod.__dict__
        globs.update(extension)
        doctest.testmod(mod, verbose=verbose, report=0, globs=globs)
    doctest.master.summarize()

if __name__ == "__main__": _test()
