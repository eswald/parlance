r'''Test cases for the Parlance server
    Copyright (C) 2004-2008  Eric Wald
    
    This module tests basic language and validation issues.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

import unittest

from parlance.functions  import fails
from parlance.tokens     import AMY, DRW, ERR, FLT, HUH, MDF, UNO
from parlance.validation import Validator
from parlance.xtended    import ENG, FRA, BRE, ECH, EDI, LON, PAR, WAL

class ValidatorTestCase(unittest.TestCase):
    def setUp(self):
        self.validator = Validator(8000)
    @fails
    def test_short_draw(self):
        message = DRW (ENG)
        reply = self.validator.validate_client_message(message)
        self.failUnlessEqual(reply, HUH (DRW, (ENG, ERR)))
    def test_empty_mdf_uno(self):
        message = MDF (ENG, FRA) ([(ENG, LON, EDI), (FRA, PAR, BRE), (UNO,)],
            [WAL, ECH]) ([LON, (AMY, WAL), (FLT, ECH, WAL)],
            [ECH, (FLT, LON, BRE)])
        reply = self.validator.validate_server_message(message)
        self.failUnlessEqual(reply, False)

if __name__ == '__main__': unittest.main()
