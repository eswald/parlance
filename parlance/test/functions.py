r'''Test cases for miscellaneous Parlance functions
    Copyright (C) 2008  Eric Wald
    
    This module tests various functions and other items that don't quite fit
    in any other test modules at this point.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

import unittest

from parlance.functions import EntryPointContainer
from parlance.player import HoldBot

class EntryPointTestCase(unittest.TestCase):
    def setUp(self):
        self.bots = EntryPointContainer("parlance.bots")
    
    def assertContains(self, item, series):
        self.failUnless(item in series,
            "Expected %r among %r" % (item, series))
    
    def test_iteration(self):
        names = list(self.bots)
        self.assertContains("HoldBot", names)
    def test_contains(self):
        self.assertContains("HoldBot", self.bots)
    def test_load(self):
        self.assertEqual(self.bots["HoldBot"], HoldBot)
    def test_unfound(self):
        self.assertRaises(KeyError, lambda: self.bots["Unknown"])
    def test_lower(self):
        self.assertEqual(self.bots["holdbot"], HoldBot)
    def test_upper(self):
        self.assertEqual(self.bots["HOLDBOT"], HoldBot)

if __name__ == '__main__':
    unittest.main()
