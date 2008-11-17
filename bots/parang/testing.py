r'''Test cases for Parang bots
    Copyright (C) 2004-2008  Eric Wald
    
    This software may be reused for non-commercial purposes without charge,
    and without notifying the authors.  Use of any part of this software for
    commercial purposes without permission from the authors is prohibited.
'''#'''

import unittest

from parlance.config       import variants
from parlance.functions    import Infinity
from parlance.gameboard    import Variant
from parlance.language     import protocol
from parlance.tokens       import *
from parlance.player       import HoldBot
from parlance.xtended      import *
from parlance.test.player  import BotTestCase
from parlance.test.network import NetworkTestCase

from parang.blabberbot import BlabberBot
from parang.combobot   import ComboBot
from parang.dumbbot    import DumbBot
from parang.evilbot    import EvilBot
from parang.neurotic   import Neurotic
from parang.peacebot   import PeaceBot
from parang.project20m import Project20M
from parang.teddybot   import TeddyBot

class BlabberBotTestCase(BotTestCase):
    bot_class = BlabberBot
    
    def test_alone(self):
        # BlabberBot used to cry if it had nobody to talk to.
        self.variant = alone = Variant("alone")
        information = '''
            [homes]
            ENG=LON
            [ownership]
            ENG=LON
            [borders]
            WAL=AMY LON, FLT ECH
            LON=AMY WAL, FLT ECH NTH
            ECH=FLT NTH LON WAL
            NTH=FLT ECH LON
        '''#"""#'''
        alone.parse(line.strip() for line in information.splitlines())
        alone.rep = alone.tokens()
        self.failUnlessComplete(None, None, alone.rep["ENG"])
    def test_seasons(self):
        # Slight API change in the Map class went unnoticed for a time.
        self.start_game()
        season = self.player.random_category("Phases")
        self.failUnlessEqual(season.category, protocol.token_cats["Phases"])

class DumbBotTestCase(BotTestCase):
    bot_class = DumbBot

class ComboBotTestCase(BotTestCase):
    bot_class = ComboBot

class EvilBotTestCase(BotTestCase):
    bot_class = EvilBot

class NeuroticTestCase(BotTestCase):
    bot_class = Neurotic
    def setUp(self):
        BotTestCase.setUp(self)
        self.variant = variants['hundred3']
    
    def test_neurotic_duplication(self):
        self.connect_player(Neurotic)
        self.start_game()
        first_result = [message
                for message in self.replies if message[0] == SUB]
        
        self.replies = []
        self.send(self.variant.start_now)
        second_result = [message
                for message in self.replies if message[0] == SUB]
        self.failUnlessEqual(first_result, second_result)

class PeaceBotTestCase(BotTestCase):
    bot_class = PeaceBot

class TeddyBotTestCase(BotTestCase):
    bot_class = TeddyBot
    
    def assertOrder(self, now, sco, country, order):
        self.assertOrders(now, sco, country, [order])
    def assertOrders(self, now, sco, country, orders):
        self.start_game(now, sco, country)
        obtained = sum((msg.fold()[1:]
                for msg in self.replies if msg[0] is SUB), [])
        for order in orders:
            self.assertContains(order, obtained)
    
    # Fall
    def test_neutral_opportunity(self):
        # Teddy takes a completely open center in the Fall
        now = NOW (FAL, 1901) (TUR, AMY, CON)
        expected = [[TUR, AMY, CON], MTO, BUL]
        self.assertOrder(now, None, TUR, expected)
    def test_central_opportunity(self):
        # Given a choice, Teddy prefers a more central center
        now = NOW (FAL, 1901) (TUR, AMY, LVN)
        expected = [[TUR, AMY, LVN], MTO, WAR]
        self.assertOrder(now, None, TUR, expected)
    def test_island_opportunity(self):
        # Given a choice, Teddy prefers a more central center
        now = NOW (FAL, 1901) (TUR, FLT, WAL)
        expected = [[TUR, FLT, WAL], MTO, LON]
        self.assertOrder(now, None, TUR, expected)
    def test_unopposed_opportunity(self):
        # Teddy takes uncontested centers first
        now = NOW (FAL, 1901) (TUR, AMY, BUR) (GER, AMY, KIE) (FRA, AMY, GAS)
        expected = [[TUR, AMY, BUR], MTO, BEL]
        self.assertOrder(now, None, TUR, expected)
    def test_unowned_opportunity(self):
        # Teddy prefers to take new centers over moving into his own
        now = NOW (FAL, 1901) (TUR, AMY, BUR)
        sco = SCO (AUS, BUD, TRI, VIE) (ENG, LVP, EDI, LON) (FRA, BRE, PAR) \
            (GER, KIE, BER) (ITA, ROM, NAP, VEN) (RUS, STP, MOS, WAR, SEV) \
            (TUR, ANK, CON, SMY, MAR, MUN, BEL) \
            (UNO, NWY, SWE, DEN, HOL, SPA, POR, TUN, GRE, SER, RUM, BUL)
        expected = [[TUR, AMY, BUR], MTO, PAR]
        self.assertOrder(now, sco, TUR, expected)
    def test_leader_opportunity(self):
        # Teddy attacks anyone close to winning
        now = NOW (FAL, 1901) (TUR, AMY, BUR)
        sco = SCO (AUS, BUD) (ENG, EDI, LVP, LON, BEL) \
            (FRA, BRE, PAR) (GER, KIE, BER, MUN) \
            (ITA, ROM, NAP, VEN, TRI, VIE, MAR, DEN, HOL,
                SPA, POR, TUN, GRE, SER, RUM, BUL, MOS, WAR) \
            (RUS, STP, SEV) (TUR, ANK, CON, SMY) (UNO, NWY, SWE)
        expected = [[TUR, AMY, BUR], MTO, MAR]
        self.assertOrder(now, sco, TUR, expected)
    
    def test_build_fleet(self):
        # Teddy makes reasonable building decisions
        now = NOW (WIN, 1901) (ENG, AMY, YOR) (ENG, AMY, WAL)
        expected = [[ENG, FLT, LON], BLD]
        self.assertOrder(now, None, ENG, expected)
    def test_two_armies(self):
        # Teddy can build two units in the same phase
        now = NOW (WIN, 1901) (AUS, FLT, TRI)
        expected = [[[AUS, AMY, VIE], BLD],
            [[AUS, AMY, BUD], BLD]]
        self.assertOrders(now, None, AUS, expected)

class CentralityTestCase(unittest.TestCase):
    r"""Low-level unit tests for TeddyBot's internal calculations.
        Currently tests its distance and centrality computations.
    """#'''#"""
    bot_class = TeddyBot
    
    def setUp(self):
        player = self.bot_class(send_method=self.handle_message,
            representation=standard.rep)
        player.map = standard_map
        self.distance = player.calc_distances()
        self.centrality = player.calc_centrality(self.distance)
    def handle_message(self, message):
        # Ignore messages from the player
        pass
    
    def test_fleet_distance(self):
        dist = self.distance[((FLT, POR, None), (FLT, FIN, None))]
        self.failUnlessEqual(dist, 6)
    def test_fleet_distance_coastal(self):
        dist = self.distance[((FLT, SPA, NCS), (FLT, PIE, None))]
        self.failUnlessEqual(dist, 4)
    def test_fleet_distance_coastal_crawl(self):
        # Fleets distance doesn't allow coast switching
        dist = self.distance[((FLT, MAR, None), (FLT, GAS, None))]
        self.failUnlessEqual(dist, 3)
    def test_fleet_distance_self(self):
        dist = self.distance[((FLT, POR, None), (FLT, POR, None))]
        self.failUnlessEqual(dist, 0)
    def test_army_distance(self):
        dist = self.distance[((AMY, POR, None), (AMY, FIN, None))]
        self.failUnlessEqual(dist, 8)
    def test_army_distance_infinity(self):
        dist = self.distance[((AMY, TUN, None), (AMY, NAP, None))]
        self.failUnlessEqual(dist, Infinity)
    def test_army_distance_self(self):
        dist = self.distance[((AMY, POR, None), (AMY, POR, None))]
        self.failUnlessEqual(dist, 0)
    def test_convoy_distance(self):
        dist = self.distance[(POR, FIN)]
        self.failUnlessEqual(dist, 5)
    def test_convoy_distance_self(self):
        dist = self.distance[(POR, POR)]
        self.failUnlessEqual(dist, 0)
    
    def test_land_centrality(self):
        self.failUnless(self.centrality[MUN] > self.centrality[SYR])

class HuffTestCase(BotTestCase):
    bot_class = Project20M

class FullBotGames(NetworkTestCase):
    "Functional tests, pitting bots against each other."
    def test_one_dumbbot(self):
        ''' Six drawing holdbots and a dumbbot'''
        self.set_verbosity(1)
        self.connect_server([DumbBot, HoldBot, HoldBot,
                HoldBot, HoldBot, HoldBot, HoldBot])
    def test_dumbbots(self):
        ''' seven dumbbots, quick game'''
        self.set_verbosity(5)
        self.connect_server([DumbBot] * 7)
    def test_evilbots(self):
        ''' Six drawing evilbots and a holdbot'''
        self.set_verbosity(4)
        #self.set_option('MTL', 10)
        #self.set_option('validate', False)
        #self.set_option('send_ORD', True)
        EvilBot.games.clear()
        self.connect_server([HoldBot, EvilBot, EvilBot,
                EvilBot, EvilBot, EvilBot, EvilBot])
    def test_neurotic(self):
        ''' One Neurotic against two EvilBots.'''
        self.set_verbosity(14)
        self.set_option('send_ORD', True)
        self.set_option('variant', 'hundred3')
        self.set_option('quit', True)
        EvilBot.games.clear()
        self.connect_server([Neurotic, EvilBot, EvilBot])

if __name__ == '__main__': unittest.main()
