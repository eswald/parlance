r'''Test cases for Parang bots
    Copyright (C) 2004-2008  Eric Wald
    
    This software may be reused for non-commercial purposes without charge,
    and without notifying the authors.  Use of any part of this software for
    commercial purposes without permission from the authors is prohibited.
'''#'''

import unittest

from parlance.player       import HoldBot
from parlance.gameboard    import Variant
from parlance.language     import protocol
from parlance.tokens       import HUH, SUB
from parlance.test.player  import BotTestCase
from parlance.test.network import NetworkTestCase

from parang.blabberbot import BlabberBot
from parang.combobot   import ComboBot
from parang.dumbbot    import DumbBot
from parang.evilbot    import EvilBot
from parang.neurotic   import Neurotic
from parang.peacebot   import PeaceBot
from parang.project20m import Project20M

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
