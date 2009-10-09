# encoding: utf-8
r'''Test cases for the Parlance server
    Copyright (C) 2004-2009  Eric Wald
    
    This module tests basic language and validation issues.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

import unittest

from parlance.language   import Message, StringToken, protocol
from parlance.test       import fails
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
    def test_bignum_valid(self):
        # Bignum tokens are valid number extensions
        message = IAM (ENG) (123456)
        reply = self.validator.validate_client_message(message)
        self.failUnlessEqual(reply, False)
    def test_bignum_invalid(self):
        # Bignum tokens are not valid where a number is expected
        bignum = protocol.default_rep[0x4C4C]
        message = IAM (ENG) (bignum)
        reply = self.validator.validate_client_message(message)
        self.failUnlessEqual(reply, HUH (IAM (ENG) (ERR, bignum)))

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
    def test_translate_bignum(self):
        msg = protocol.default_rep.translate("TME (123456)")
        self.failUnlessEqual(msg, TME (123456))
    def test_bignum_str(self):
        msg = TME (123456)
        self.failUnlessEqual(str(msg), "TME ( 123456 )")
    def test_invalid_bignum_str(self):
        msg = TME (123456)
        msg.pop(2)
        self.failUnlessEqual(str(msg), "TME ( 0x4C40 )")

class NumberTestCase(unittest.TestCase):
    def check_number_code(self, number, code):
        msg = TME (number)
        packed = map(ord, msg.pack())[4:-2]
        self.assertEqual(packed, code, repr(map(hex, packed)))
    
    def test_zero(self):
        self.check_number_code(0, [0x00, 0x00])
    def test_one(self):
        self.check_number_code(1, [0x00, 0x01])
    def test_negative_one(self):
        self.check_number_code(-1, [0x3F, 0xFF])
    def test_largest_positive(self):
        self.check_number_code(0x1fff, [0x1F, 0xFF])
    def test_largest_negative(self):
        self.check_number_code(-0x2000, [0x20, 0x00])
    
    def test_bignum_positive(self):
        # 123456 = 0x01E240
        self.check_number_code(123456, [0x01, 0xE2, 0x4C, 0x40])
    def test_bignum_negative(self):
        # -123456 = ...1110_0001_1101_1100_0000 = 0xFE1DC0
        self.check_number_code(-123456, [0x3E, 0x1D, 0x4C, 0xC0])
    def test_barely_bignum(self):
        self.check_number_code(0x2000, [0x00, 0x20, 0x4C, 0x00])
    def test_largest_bignum(self):
        self.check_number_code(0x1fffff, [0x1F, 0xFF, 0x4C, 0xFF])
    def test_barely_double_bignum(self):
        self.check_number_code(0x200000, [0x00, 0x20, 0x4C, 0x00, 0x4C, 0x00])
    def test_barely_bignum_negative(self):
        self.check_number_code(-0x2001, [0x3F, 0xDF, 0x4C, 0xFF])

class NumberFoldingTestCase(NumberTestCase):
    def check_number_code(self, number, code):
        bytes = [0x48, 0x1B, 0x40, 0x00] + code + [0x40, 0x01]
        packed = "".join(map(chr, bytes))
        msg = protocol.default_rep.unpack(packed)
        obtained = msg.fold()[1][0]
        self.assertEqual(obtained, number, repr(msg))

class NumberReprTestCase(NumberTestCase):
    def check_number_code(self, number, code):
        msg = TME (number)
        obtained = repr(msg)
        expected = "Message([TME, [" + repr(number) + "]])"
        self.assertEqual(obtained, expected)

if __name__ == '__main__': unittest.main()
