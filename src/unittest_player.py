''' Unit tests for the PyDip player module
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
'''#'''

import unittest, config
from functions import Verbose_Object, relative_limit, version_string
from player    import Player, HoldBot
from language  import *

__version__ = "$Revision$"

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
            'syntax Level': 8000,
            'Partial Draws Allowed': True,
            'default variant' : 'standard',
            'close on disconnect' : True,
            'host' : '',
            'publish order sets': False,
            'publish individual orders': False,
            'total years before setting draw': 3,
            'invalid message response': 'die',
    }
    def setUp(self):
        ''' Initializes class variables for test cases.'''
        self.set_verbosity(0)
        config.option_class.local_opts.update(self.game_options)
        self.variant = config.variants['standard']
        opts = config.game_options()
        self.params = opts.get_params()
        self.level = opts.LVL
        self.player = None
        self.replies = []
    def handle_message(self, message):
        #print message
        reply = message.validate(self.level)
        self.failIf(reply, reply)
        self.replies.append(message)
    def tearDown(self):
        if self.player: self.send(OFF())
    def set_verbosity(self, verbosity): Verbose_Object.verbosity = verbosity
    def send(self, message): self.player.handle_message(message)
    def accept(self, message): self.send(YES(message))
    def rejept(self, message): self.send(REJ(message))
    def connect_player(self, player_class, **kwargs):
        self.player = player_class(self.handle_message, self.variant.rep, **kwargs)
    def send_hello(self, country=None):
        from xtended import ENG
        self.send(HLO(country or ENG, self.level, self.params))
    def seek_reply(self, message, error=None):
        while self.replies:
            msg = self.replies.pop(0)
            if msg == message: break
        else: self.fail(error or 'Expected: ' + str(message))
    def start_game(self):
        while self.replies:
            msg = self.replies.pop(0)
            if msg[0] is NME: self.accept(msg); break
        else: self.fail('No NME message')
        self.send(MAP(self.variant.map_name))
        while self.replies:
            msg = self.replies.pop(0)
            if msg[0] is MDF: self.send(self.variant.map_mdf)
            elif msg[0] is YES and msg[2] is MAP: break
        else: self.fail('Failed to accept the map')
        self.send_hello()
        self.send(self.variant.start_sco)
        self.send(self.variant.start_now)
    def assertContains(self, item, series):
        self.failUnless(item in series, 'Expected %r among %r' % (item, series))

class Player_Tests(PlayerTestCase):
    class Test_Player(Player):
        name = 'Test Player'
        version = version_string(__version__)
        def handle_REJ_YES(self, message): self.send(HLO())
        def handle_press_SUG(self, *args):
            raise NotImplementedError, 'Intentionally raising an error.'
        def generate_orders(self): pass
    def test_press_response(self):
        from xtended import ENG, FRA, GER
        self.connect_player(self.Test_Player)
        self.start_game()
        self.replies = []
        offer = PRP(PCE([ENG, FRA]))
        self.send(FRM([FRA, 0], ENG, offer))
        self.seek_reply(SND(Number, FRA, HUH([ERR, offer])) + WRT([FRA, 0]))
        self.seek_reply(SND(Number, FRA, TRY([])))
    def test_validate_option(self):
        self.connect_player(self.Test_Player)
        self.player.client_opts.validate = False
        self.send(REJ(YES))
        self.assertContains(HLO(), self.replies)
        self.failIf(self.player.closed)
        self.player.client_opts.validate = True
        self.send(REJ(YES))
        self.failUnless(self.player.closed)
    def test_known_map(self):
        self.connect_player(self.Test_Player)
        self.seek_reply(NME(self.Test_Player.name, self.Test_Player.version))
        self.send(MAP('fleet_rome'))
        self.seek_reply(YES(MAP('fleet_rome')))
    def test_unknown_map(self):
        self.connect_player(self.Test_Player)
        self.seek_reply(NME(self.Test_Player.name, self.Test_Player.version))
        self.send(MAP('unknown'))
        self.seek_reply(MDF())
        self.send(config.variants['fleet_rome'].map_mdf)
        self.seek_reply(YES(MAP('unknown')))
    def test_HLO_PDA(self):
        ''' The HLO message should be valid with level 10 parameters.'''
        self.connect_player(self.Test_Player)
        self.player.client_opts.validate = True
        self.start_game()
        self.failIf(self.player.closed)
    def test_press_error(self):
        ''' Errors in handle_press methods should send HUH(message ERR) press.'''
        from xtended import ENG, GER
        self.connect_player(self.Test_Player)
        self.start_game()
        offer = SUG(DRW)
        self.send(FRM([GER, 0], ENG, offer))
        self.seek_reply(SND(Number, GER, HUH([offer, ERR])) + WRT([GER, 0]))

class Player_HoldBot(PlayerTestCase):
    def setUp(self):
        PlayerTestCase.setUp(self)
        self.connect_player(HoldBot)
    def test_press_response(self):
        from xtended import ENG, FRA, GER
        self.start_game()
        self.replies = []
        offer = PRP(PCE([ENG, FRA]))
        self.send(FRM([FRA, 0], ENG, offer))
        self.seek_reply(SND(Number, FRA, HUH([ERR, offer])) + WRT([FRA, 0]))
        self.seek_reply(SND(Number, FRA, TRY([])))

class Player_Bots(PlayerTestCase):
    def setUp(self):
        def handle_NOW(player, message):
            ''' Non-threading version of Player.handle_NOW().'''
            if player.in_game and player.power:
                from orders import OrderSet
                player.submitted = False
                player.orders = OrderSet(player.power)
                if player.missing_orders():
                    player.generate_orders()
            else: self.fail('Player failed to join the game.')
        def handle_HUH(player, message):
            ''' Fail on bad message submission.'''
            self.fail('Server complained about a message: ' + str(message))
        def handle_THX(player, message):
            ''' Fail on bad order submission.'''
            self.fail('Invalid order submitted: ' + str(message))
        PlayerTestCase.setUp(self)
        Player.handle_NOW = handle_NOW
        Player.handle_THX = handle_THX
    
    def test_project20m(self):
        ''' Demonstrates that Project20M can at least survive a single season.
        '''#'''
        from project20m import Project20M
        self.connect_player(Project20M)
        self.start_game()
        self.assertContains(SUB, [message[0] for message in self.replies])

if __name__ == '__main__': unittest.main()
