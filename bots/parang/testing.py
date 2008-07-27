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
from parlance.tokens       import SUB
from parlance.player       import HoldBot
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
        self.start_game(now, sco, country)
        orders = sum((msg.fold()[1:]
                for msg in self.replies if msg[0] is SUB), [])
        self.assertContains(order, orders)
    
    def test_fall_opportunity(self):
        # Teddy takes a completely open center in the Fall
        from parlance.tokens import NOW, FAL, AMY, MTO
        from parlance.xtended import TUR, CON, BUL
        now = NOW (FAL, 1901) (TUR, AMY, CON)
        expected = [[TUR, AMY, CON], MTO, BUL]
        self.assertOrder(now, None, TUR, expected)
    
    def test_fleet_distance(self):
        from parlance.tokens import FLT
        from parlance.xtended import POR, FIN
        self.start_game()
        dist = self.player.distance[((FLT, POR, None), (FLT, FIN, None))]
        self.failUnlessEqual(dist, 6)
    def test_fleet_distance_coastal(self):
        from parlance.tokens import FLT, NCS
        from parlance.xtended import SPA, PIE
        self.start_game()
        dist = self.player.distance[((FLT, SPA, NCS), (FLT, PIE, None))]
        self.failUnlessEqual(dist, 4)
    def test_fleet_distance_coastal_crawl(self):
        # Fleets distance doesn't allow coast switching
        from parlance.tokens import FLT
        from parlance.xtended import MAR, GAS
        self.start_game()
        dist = self.player.distance[((FLT, MAR, None), (FLT, GAS, None))]
        self.failUnlessEqual(dist, 3)
    def test_fleet_distance_self(self):
        from parlance.tokens import FLT
        from parlance.xtended import POR
        self.start_game()
        dist = self.player.distance[((FLT, POR, None), (FLT, POR, None))]
        self.failUnlessEqual(dist, 0)
    def test_army_distance(self):
        from parlance.tokens import AMY
        from parlance.xtended import POR, FIN
        self.start_game()
        dist = self.player.distance[((AMY, POR, None), (AMY, FIN, None))]
        self.failUnlessEqual(dist, 8)
    def test_army_distance_infinity(self):
        from parlance.tokens import AMY
        from parlance.xtended import TUN, NAP
        self.start_game()
        dist = self.player.distance[((AMY, TUN, None), (AMY, NAP, None))]
        self.failUnlessEqual(dist, Infinity)
    def test_army_distance_self(self):
        from parlance.tokens import AMY
        from parlance.xtended import POR
        self.start_game()
        dist = self.player.distance[((AMY, POR, None), (AMY, POR, None))]
        self.failUnlessEqual(dist, 0)
    def test_convoy_distance(self):
        from parlance.xtended import POR, FIN
        self.start_game()
        dist = self.player.distance[(POR, FIN)]
        self.failUnlessEqual(dist, 5)
    def test_convoy_distance_self(self):
        from parlance.xtended import POR
        self.start_game()
        dist = self.player.distance[(POR, POR)]
        self.failUnlessEqual(dist, 0)
    
    def test_land_centrality(self):
        from parlance.xtended import MUN, SYR
        self.start_game()
        centrality = self.player.centrality
        self.failUnless(centrality[MUN] > centrality[SYR])

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
