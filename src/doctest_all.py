''' PyDip docstring testing
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
    
    When run, this module runs docstring tests in other modules.
    Some modules requre at least Python 2.4 for doctests.
'''#'''

def _test():
    import doctest, sys
    
    import config
    import gameboard
    import dumbbot
    import language
    import main
    import network
    import player
    import server
    import translation
    import validation
    
    # List of modules to test
    modules = [
        gameboard,
        config,
        dumbbot,
        language,
        main,
        network,
        player,
        server,
        translation,
        validation,
    ]
    
    extension = config.extend_globals(dict([(k,v)
        for k,v in language.__dict__.iteritems() if k[0] != '_']))
    verbose = "-v" in sys.argv
    
    for mod in modules:
        print 'Testing', mod.__name__
        language.Token.opts.squeeze_parens = False
        language.Token.opts.escape_char = '"'
        language.Token.opts.quot_char = '"'
        globs = mod.__dict__
        globs.update(extension)
        doctest.testmod(mod, verbose=verbose, report=0, globs=globs)
    doctest.master.summarize()

if __name__ == "__main__": _test()
