# encoding: utf-8
r'''Test cases for the Parlance server
    Copyright (C) 2004-2009  Eric Wald
    
    This module tests basic language and validation issues.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

import unittest

from parlance.functions  import fails
from parlance.language   import Message, StringToken
from parlance.tokens     import *
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
    def test_mistaken_prn(self):
        message = SND (FRA) (PRP (SCD (ENG)))
        reply = self.validator.validate_client_message(message)
        self.failUnlessEqual(reply, HUH (SND (FRA) (PRP (SCD (ENG, ERR)))))
    def test_invalid_encoding(self):
        # ERR gets placed before the first undecodable character.
        message = NME ("Tom\xe1s") ("v1.3")
        reply = self.validator.validate_client_message(message)
        self.failUnlessEqual(reply, HUH (NME ("Tom", ERR, "\xe1s") ("v1.3")))

class LanguageTestCase(unittest.TestCase):
    greek = u"Καλημέρα κόσμε"
    def test_unicode_param(self):
        msg = NME (self.greek) (u"v1.3")
    def test_unicode_folding(self):
        name = [StringToken(c) for c in self.greek.encode("utf-8")]
        msg = Message([NME, name, [u"v1.3"]])
        self.failUnlessEqual(msg.fold()[1][0], self.greek)
    def test_invalid_encoding_repr(self):
        msg = NME ("Tom\xe1s") ("v1.3")
        expected = ("Message([NME, [StringToken('T'), StringToken('o'), " +
            "StringToken('m'), StringToken('\\xe1'), StringToken('s')], " +
            "[u'v1.3']])")
        self.failUnlessEqual(repr(msg), expected)

if __name__ == '__main__': unittest.main()
