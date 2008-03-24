r'''Parterre variant loader
    Copyright (C) 2008  Eric Wald
    
    This module provides the entry point for exporting variants to Parlance.
    
    This package may be reused for non-commercial purposes without charge,
    and without notifying the authors.  Use of any part of this package for
    commercial purposes without permission from the authors is prohibited.
'''#"""#'''

from parlance.gameboard import Variant

class Loader(object):
    def __getattr__(self, name):
        resource = "resource://%s/data/%s.cfg" % (__name__, name)
        print "Loading", resource
        variant = Variant(name, filename=resource)
        setattr(self, name, variant)
        return variant

loader = Loader()
