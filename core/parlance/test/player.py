r'''Test cases for Parlance clients
    Copyright (C) 2004-2008  Eric Wald
    
    This module tests the basic client classes of the framework, as well as
    the HoldBot player based on them.  Other bots should have their own test
    scripts, but may use the tests in here as a base.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

import unittest

from parlance.config     import Configuration, GameOptions
from parlance.gameboard  import Map, Variant
from parlance.judge      import DatcOptions
from parlance.language   import Token
from parlance.orders     import OrderSet, createUnitOrder
from parlance.player     import AutoObserver, Player, HoldBot
from parlance.tokens     import *
from parlance.validation import Validator
from parlance.xtended    import *

class NumberToken(object):
    def __eq__(self, other):
        if isinstance(other, Token): return other.is_integer()
        else: return NotImplemented
    def tokenize(self): return [self]
    def __repr__(self): return 'NumberToken'
    def __radd__(self, other): return other + ' #'
Number = NumberToken()

class PlayerTestCase(unittest.TestCase):
    ''' Basic Player Functionality'''
    
    game_options = {
        'LVL': 8000,
        'PDA': True,
        'variant' : 'standard',
        'quit' : True,
        'host' : '',
        'send_SET': False,
        'send_ORD': False,
        'draw': 3,
        'response': 'die',
    }
    def setUp(self):
        ''' Initializes class variables for test cases.'''
        self.set_verbosity(0)
        Configuration._cache.update(self.game_options)
        self.variant = standard
        opts = GameOptions()
        self.params = opts.get_params()
        self.level = opts.LVL
        self.validator = Validator(opts.LVL)
        self.player = None
        self.replies = []
    def handle_message(self, message):
        #print message
        reply = self.validator.validate_client_message(message)
        self.failIf(reply, reply)
        self.replies.append(message)
    def tearDown(self):
        if self.player: self.send(+OFF)
    def set_verbosity(self, verbosity):
        Configuration.set_globally('verbosity', verbosity)
    def send(self, message): self.player.handle_message(message)
    def accept(self, message): self.send(YES(message))
    def reject(self, message): self.send(REJ(message))
    def connect_player(self, player_class, **kwargs):
        self.player = player_class(send_method=self.handle_message,
                representation=self.variant.rep, **kwargs)
        self.player.register()
        self.player.threaded = []
    def send_hello(self, country=None):
        self.send(HLO(country or ENG)(self.level)(self.params))
    def seek_reply(self, message, error=None):
        while self.replies:
            msg = self.replies.pop(0)
            if msg == message: break
        else: self.fail(error or 'Expected: ' + str(message))
    def start_game(self, now=None, sco=None, country=None):
        while self.replies:
            msg = self.replies.pop(0)
            if msg[0] is NME: self.accept(msg); break
        else: self.fail('No NME message')
        self.send(MAP(self.variant.mapname))
        while self.replies:
            msg = self.replies.pop(0)
            if msg[0] is MDF: self.send(self.variant.mdf())
            elif msg[0] is YES and msg[2] is MAP: break
        else: self.fail('Failed to accept the map')
        self.send_hello(country)
        self.send(sco or self.variant.sco())
        self.send(now or self.variant.now())
    def assertContains(self, item, series):
        self.failUnless(item in series, 'Expected %r among %r' % (item, series))

class Player_Tests(PlayerTestCase):
    class Test_Player(Player):
        def handle_REJ_YES(self, message): self.send(+HLO)
        def handle_press_THK(self, sender, press):
            self.send_press(sender, WHY(press))
        def handle_press_SUG(self, *args):
            raise NotImplementedError, 'Intentionally raising an error.'
        def generate_orders(self): pass
    def test_press_response(self):
        self.connect_player(self.Test_Player)
        self.start_game()
        self.replies = []
        offer = PRP(PCE(ENG, FRA))
        self.send(FRM(FRA)(ENG)(offer))
        self.seek_reply(SND(FRA)(HUH(ERR + offer)))
        self.seek_reply(SND(FRA)(TRY()))
    def test_press_response_legacy(self):
        # Same as above, but with WRT syntax
        # Note that this only works with validation off.
        self.connect_player(self.Test_Player)
        self.start_game()
        self.replies = []
        offer = THK(PCE(ENG, GER))
        self.player.validator = None
        self.send(FRM(FRA, 0)(ENG)(offer) + WRT(ENG, 0))
        self.seek_reply(SND(FRA)(WHY(offer)))
    def test_validate_option(self):
        # Todo: Fix this test to actually test the client_opts option again.
        self.connect_player(self.Test_Player)
        validator = self.player.validator
        self.player.validator = None
        self.send(REJ(YES))
        self.seek_reply(+HLO)
        self.failIf(self.player.closed)
        self.player.validator = validator or Validator()
        self.send(REJ(YES))
        self.failUnless(self.player.closed)
    def test_known_map(self):
        self.connect_player(self.Test_Player)
        self.seek_reply(NME (self.player.name) (self.player.version))
        self.send(MAP('standard'))
        self.seek_reply(YES(MAP('standard')))
    def test_unknown_map(self):
        self.connect_player(self.Test_Player)
        self.seek_reply(NME (self.player.name) (self.player.version))
        self.send(MAP('unknown'))
        self.seek_reply(+MDF)
        self.send(standard.mdf())
        self.seek_reply(YES(MAP('unknown')))
    def test_HLO_PDA(self):
        ''' The HLO message should be valid with level 10 parameters.'''
        self.connect_player(self.Test_Player)
        if not self.player.validator: self.player.validator = Validator()
        self.start_game()
        self.failIf(self.player.closed)
    def test_press_error(self):
        ''' Errors in handle_press methods should send HUH(message ERR) press.'''
        self.connect_player(self.Test_Player)
        self.start_game()
        offer = SUG(DRW)
        self.send(FRM(GER)(ENG)(offer))
        self.seek_reply(SND(GER)(HUH(offer ++ ERR)))
    def test_AutoObserver(self):
        ''' Former doctests of the AutoObserver class.'''
        result = []
        def handle_message(msg):
            if msg[0] is ADM:
                result.append(msg)
                player.handle_ADM(msg)
        player = AutoObserver(send_method=handle_message,
                representation=self.variant.rep)
        player.handle_ADM(ADM('Server')('An Observer has connected. '
            'Have 5 players and 1 observers. Need 2 to start'))
        player.handle_ADM(ADM('Geoff')('Does the observer want to play?'))
        self.failUnlessEqual(result[-1],
                ADM ( "AutoObserver" ) ( "Sorry; I'm just a bot." ))
        player.handle_ADM(ADM('Geoff')('Are you sure about that?'))
        self.failUnlessEqual(result[-1],
                ADM ( "AutoObserver" ) ( "Yes, I'm sure." ))
        player.handle_ADM(ADM('DanM')('Do any other observers care to jump in?'))
        self.failUnlessEqual(len(result), 2)
    def test_uppercase_mapname(self):
        ''' Clients should recognize map names in upper case.'''
        self.connect_player(self.Test_Player)
        while self.replies:
            msg = self.replies.pop(0)
            if msg[0] is NME: self.accept(msg); break
        else: self.fail('No NME message')
        msg = MAP(self.variant.mapname.upper())
        self.send(msg)
        self.seek_reply(YES(msg))
    def test_HUH_bounce(self):
        ''' A client should deal with HUH response to its HUH message.'''
        Configuration.set_globally('validate', True)
        Configuration.set_globally('response', 'complain')
        #self.set_verbosity(7)
        self.connect_player(self.Test_Player)
        while self.replies:
            msg = self.replies.pop(0)
            if msg[0] is NME: self.accept(msg); break
        else: self.fail('No NME message')
        # Syntactically incorrect message, just to prompt HUH
        self.send(MAP(0))
        self.seek_reply(HUH(MAP(ERR, 0)))
        self.send(HUH(ERR, HUH(MAP(ERR, 0))))
        self.failUnlessEqual(self.replies, [])

class Player_HoldBot(PlayerTestCase):
    r'''Test cases specific to the HoldBot class.
        These could go in a subclass of BotTestCase,
        but that would run each case of the latter twice.
    '''#"""#'''
    
    def setUp(self):
        PlayerTestCase.setUp(self)
        self.connect_player(HoldBot)
    def test_press_response(self):
        self.start_game()
        self.replies = []
        offer = PRP(PCE(ENG, FRA))
        self.send(FRM(FRA)(ENG)(offer))
        self.seek_reply(SND(FRA)(HUH(ERR + offer)))
        self.seek_reply(SND(FRA)(TRY()))

class BotTestCase(PlayerTestCase):
    r'''Test cases applicable to all computer players.
        When subclassing, override the bot_class variable.
        Subclasses may also include bot-specific tests, if desired.
    '''#"""#'''
    
    bot_class = HoldBot
    
    def setUp(self):
        PlayerTestCase.setUp(self)
        self.connect_player(self.bot_class)
    def handle_message(self, message):
        self.failIfEqual(message[0], HUH, message)
        PlayerTestCase.handle_message(self, message)
    def failUnlessComplete(self, now, sco, country):
        orders = OrderSet()
        datc = DatcOptions()
        board = Map(self.variant)
        if sco: board.handle_SCO(sco)
        if now: board.handle_NOW(now)
        power = board.powers[country]
        phase = board.current_turn.phase()
        self.start_game(now, sco, country)
        for msg in self.replies:
            if msg[0] is SUB:
                for item in msg.fold()[1:]:
                    order = createUnitOrder(item, power, board, datc)
                    note = order.order_note(power, phase, orders)
                    self.failUnlessEqual(note, MBV)
                    orders.add(order, country)
            elif msg[0] is NOT and msg[2] is SUB:
                # Todo: Handle partial unsubmittals correctly.
                orders = OrderSet()
        result = orders.missing_orders(phase, power)
        self.failIf(result, result)
    
    # Do not use docstrings for tests here,
    # because they will make tests of different bots indistinguishable.
    def test_startup(self):
        # The bot can at least start up without complaining.
        self.start_game()
        result = [message[0] for message in self.replies]
        self.failIf(HUH in result)
    def test_any_orders(self):
        # The bot tries to submit orders for the first season.
        self.start_game()
        result = [message[0] for message in self.replies]
        self.assertContains(SUB, result)
    def test_spring_orders(self):
        # The bot can submit a complete set of orders for the spring season.
        self.failUnlessComplete(None, None, ENG)
    def test_retreat_orders(self):
        self.failUnlessComplete(
            NOW (SUM, 1901) (ENG, FLT, LON, MRT, [WAL, ECH]) (ENG, FLT, NTH),
            None, ENG)
    def test_disband_orders(self):
        self.failUnlessComplete(
            NOW (SUM, 1901) (ENG, FLT, LON, MRT, []),
            None, ENG)
    def test_removal_orders(self):
        self.failUnlessComplete(NOW (WIN, 1901)
            (ENG, FLT, LON) (ENG, AMY, WAL) (ENG, FLT, NTH) (ENG, FLT, ECH),
            None, ENG)
    def test_inland_builds(self):
        self.failUnlessComplete(NOW (WIN, 1901) (AUS, FLT, TRI), None, AUS)
    def test_coastal_builds(self):
        self.failUnlessComplete(NOW (WIN, 1901), None, ENG)
    def test_bicoastal_builds(self):
        self.failUnlessComplete(NOW (WIN, 1901)
            (RUS, FLT, SEV) (RUS, AMY, UKR) (RUS, AMY, MOS),
            None, RUS)
    def test_sea_builds(self):
        self.variant = sea = Variant("sea")
        information = '''
            [homes]
            ENG=NTH
            [ownership]
            ENG=NTH
            [borders]
            NTH=FLT ECH
            ECH=FLT NTH
        '''#"""#'''
        sea.parse(line.strip() for line in information.splitlines())
        sea.rep = sea.tokens()
        self.failUnlessComplete(NOW (WIN, 1901), None, sea.rep["ENG"])

if __name__ == '__main__': unittest.main()
