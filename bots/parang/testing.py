r'''Test cases for Parang bots
    Copyright (C) 2004-2008  Eric Wald
    
    This software may be reused for non-commercial purposes without charge,
    and without notifying the authors.  Use of any part of this software for
    commercial purposes without permission from the authors is prohibited.
'''#'''

import unittest

from parlance.player       import HoldBot
from parlance.tokens       import HUH, SUB
from parlance.test.player  import PlayerTestCase
from parlance.test.network import NetworkTestCase

from parang.blabberbot import BlabberBot
from parang.dumbbot    import DumbBot
from parang.evilbot    import EvilBot
from parang.neurotic   import Neurotic
from parang.project20m import Project20M

class Player_Bots(PlayerTestCase):
    def connect_player(self, bot_class, **kwargs):
        PlayerTestCase.connect_player(self, bot_class, **kwargs)
        def handle_THX(player, message):
            ''' Fail on bad order submission.'''
            self.fail('Invalid order submitted: ' + str(message))
        def handle_MIS(player, message):
            ''' Fail on incomplete order submission.'''
            self.fail('Missing orders: ' + str(message))
        self.player.handle_THX = handle_THX
        self.player.handle_MIS = handle_MIS
    def attempt_one_phase(self, bot_class):
        ''' Demonstrates that the given bot can at least start up
            and submit a complete set of orders for the first season.
        '''#'''
        self.connect_player(bot_class)
        self.start_game()
        result = [message[0] for message in self.replies]
        self.assertContains(SUB, result)
        self.failIf(HUH in result)
    
    def test_project20m(self):
        self.attempt_one_phase(Project20M)
    def test_blabberbot(self):
        self.attempt_one_phase(BlabberBot)
    def test_neurotic(self):
        self.variant = variants['hundred3']
        self.attempt_one_phase(Neurotic)
    def test_neurotic_duplication(self):
        self.variant = variants['hundred3']
        self.connect_player(Neurotic)
        self.start_game()
        first_result = [message
                for message in self.replies if message[0] == SUB]
        
        self.replies = []
        self.send(self.variant.start_now)
        second_result = [message
                for message in self.replies if message[0] == SUB]
        self.failUnlessEqual(first_result, second_result)

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
