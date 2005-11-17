''' Unit tests for the Player module.
'''#'''

import unittest, config
from functions import Verbose_Object
from player    import Player, HoldBot
from language  import *

def relative_limit(seconds):
    ''' Converts a number of seconds into a TME message number.
        Negative message numbers indicate hours; positive, seconds.
    '''#'''
    max_int = Token.opts.max_pos_int
    if seconds > max_int: result = -seconds // 3600
    else: result = seconds
    if -result > max_int: result = -max_int
    return result
def get_variant_list(game_options):
    variant = [(LVL, game_options.LVL)]
    if game_options.MTL: variant.append((MTL, relative_limit(game_options.MTL)))
    if game_options.RTL: variant.append((RTL, relative_limit(game_options.RTL)))
    if game_options.BTL: variant.append((BTL, relative_limit(game_options.BTL)))
    if game_options.AOA: variant.append((AOA,))
    if game_options.DSD: variant.append((DSD,))
    
    if game_options.LVL >= 10:
        if game_options.PDA: variant.append((PDA,))
        if game_options.NPR: variant.append((NPR,))
        if game_options.NPB: variant.append((NPB,))
        if game_options.PTL: variant.append((PTL, self.relative_limit(game_options.PTL)))
    return variant

class NumberToken(object):
    def __eq__(self, other):
        if isinstance(other, Token): return other.is_integer()
        else: return NotImplemented
    def tokenize(self): return [self]
Number = NumberToken()

class PlayerTestCase(unittest.TestCase):
    "Basic Player Functionality"
    
    game_options = {
            'syntax Level': 8000,
            'variant name' : 'standard',
            'close on disconnect' : True,
            'use internal server' : True,
            'host' : '',
            'port' : 16719,
            'timeout for select() without deadline' : 5,
            'publish order sets': False,
            'publish individual orders': False,
            'total years before setting draw': 3,
            'invalid message response': 'die',
    }
    def setUp(self):
        ''' Initializes class variables for test cases.'''
        self.set_verbosity(0)
        config.option_class.local_opts.update(self.game_options)
        self.variant = config.variant_options('standard')
        opts = config.game_options()
        self.params = get_variant_list(opts)
        self.level = opts.LVL
        self.player = None
        self.replies = []
    def handle_message(self, message):
        #print message
        reply = message.validate(self.player and self.player.power, self.level)
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
        self.send(HLO(country or ENG, 0, self.params))
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
        version = '$version$'
        def handle_REJ_YES(self, message): self.send(HLO())
        def generate_orders(self): pass
    def test_press_response(self):
        from xtended import ENG, FRA, GER
        self.connect_player(self.Test_Player)
        self.start_game()
        self.replies = []
        offer = PRP(PCE([ENG, FRA]))
        self.send(FRM([FRA, 0], ENG, offer))
        self.seek_reply(SND(Number, FRA, HUH(ERR() + offer)) + WRT([FRA, 0]))
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
        self.seek_reply(SND(Number, FRA, HUH(ERR() + offer)) + WRT([FRA, 0]))
        self.seek_reply(SND(Number, FRA, TRY([])))

if __name__ == '__main__': unittest.main()

# vim: sts=4 sw=4 et tw=75 fo=crql1
