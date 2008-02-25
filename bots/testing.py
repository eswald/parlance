r'''Test cases for Parlance bots
    Copyright (C) 2004-2008  Eric Wald
    
    This module contains the test cases removed from the Parlance core
    framework due to dependence on restricted or incomplete bot code.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

from blabberbot       import BlabberBot
from dumbbot          import DumbBot
from evilbot          import EvilBot
from neurotic         import Neurotic
from project20m       import Project20M
from unittest_player  import PlayerTestCase
from unittest_network import NetworkTestCase

class Player_Bots(PlayerTestCase):
    def setUp(self):
        def handle_THX(player, message):
            ''' Fail on bad order submission.'''
            self.fail('Invalid order submitted: ' + str(message))
        def handle_MIS(player, message):
            ''' Fail on incomplete order submission.'''
            self.fail('Missing orders: ' + str(message))
        PlayerTestCase.setUp(self)
        Player.handle_THX = handle_THX
        Player.handle_MIS = handle_MIS
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

class Network_Full_Games(NetworkTestCase):
    def test_one_dumbbot(self):
        ''' Six drawing holdbots and a dumbbot'''
        self.set_verbosity(1)
        self.connect_server([DumbBot, HoldBot, HoldBot,
                HoldBot, HoldBot, HoldBot, HoldBot])
    def test_dumbbots(self):
        ''' seven dumbbots, quick game'''
        self.set_verbosity(1)
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
