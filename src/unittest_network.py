''' Unit tests for the PyDip network module
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
'''#'''

import unittest, config
from time      import sleep
from functions import Verbose_Object
from unittest_server import ServerTestCase

class NetworkTestCase(ServerTestCase):
    class Disconnector(ServerTestCase.Fake_Player):
        sleep_time = 14
        name = 'Loose connection'
        def handle_message(self, message):
            from language import HLO, ADM
            self.__super.handle_message(message)
            if message[0] is HLO:
                sleep(self.sleep_time)
                self.send(ADM(str(self.power))('Passcode: %d' % self.pcode))
                self.close()
    
    def setUp(self):
        ServerTestCase.setUp(self)
        self.threads = []
    def tearDown(self):
        ServerTestCase.tearDown(self)
        for thread in self.threads:
            while thread.isAlive(): thread.join(1)
    def connect_server(self, clients, games=1, poll=True, **kwargs):
        from network import ServerSocket, Client
        from server import Server, Client_Manager
        config.option_class.local_opts.update({'number of games' : games})
        socket = ServerSocket(Server, Client_Manager())
        if not poll: socket.polling = None
        s_thread = socket.start()
        self.server = server = socket.server
        assert s_thread and server
        self.threads.append(s_thread)
        try:
            for dummy in range(games):
                assert not server.closed
                threads = []
                for player_class in clients:
                    thread = Client(player_class, **kwargs).start()
                    assert thread
                    threads.append(thread)
                for thread in threads:
                    if thread.isAlive(): thread.join()
        except:
            self.threads.extend(threads)
            server.close()
            raise
    def connect_player(self, player_class):
        from network import Client
        client = Client(player_class)
        self.threads.append(client.start())
        return client.player

class Network_Basics(NetworkTestCase):
    def test_timeout(self):
        ''' Thirty-second timeout for the Initial Message'''
        self.set_option('port', 16721)
        self.connect_server([])
        client = self.Fake_Client(None)
        client.open()
        sleep(45)
        client.read_error(client.opts.Timeout)
    def test_reserved_tokens(self):
        ''' "Reserved for AI use" tokens must never be sent over the wire.'''
        class ReservedSender(object):
            def __init__(self, send_method, rep, *args, **kwargs):
                self.send = send_method
            def register(self):
                from language import Token
                self.send(Token('HMM', 0x585F)())
        self.connect_server([])
        client = self.Fake_Client(ReservedSender)
        client.open()
        client.read_error(client.opts.IllegalToken)
    def test_full_connection(self):
        ''' Seven fake players, polling if possible'''
        self.set_verbosity(15)
        self.connect_server([self.Disconnector] * 7)
    def test_without_poll(self):
        ''' Seven fake players, selecting'''
        self.set_verbosity(15)
        self.connect_server([self.Disconnector] * 7, poll=False)
    def test_with_timer(self):
        ''' Seven fake players and an observer'''
        from player  import Clock
        self.connect_server([Clock] + ([self.Disconnector] * 7))
    def test_takeover(self):
        ''' Takeover ability after game start'''
        class Fake_Takeover(Verbose_Object):
            ''' A false player, who takes over a position and then quits.'''
            sleep_time = 7
            def __init__(self, send_method, representation, power, passcode):
                self.log_debug(9, 'Fake player started')
                self.restarted = False
                self.closed = False
                self.send = send_method
                self.rep = representation
                self.power = power
                self.passcode = passcode
            def register(self):
                from language import NME
                self.send(NME(self.power.text)(str(self.passcode)))
            def close(self):
                self.log_debug(9, 'Closed')
                self.closed = True
            def handle_message(self, message):
                from language import YES, REJ, NME, IAM, ADM
                self.log_debug(5, '<< %s', message)
                if message[0] is YES and message[2] is IAM:
                    self.send(ADM(self.power.text)('Takeover successful'))
                    sleep(self.sleep_time)
                    self.close()
                elif message[0] is REJ and message[2] is NME:
                    self.send(IAM(self.power)(self.passcode))
                elif message[0] is ADM: pass
                else: raise AssertionError, 'Unexpected message: ' + str(message)
        class Fake_Restarter(self.Disconnector):
            ''' A false player, who starts Fake_Takeover after receiving HLO.'''
            sleep_time = 3
            def close(self):
                from network import Client
                thread = Client(Fake_Takeover, power=self.power,
                    passcode=self.pcode).start()
                assert thread
                thread.join()
                self.log_debug(9, 'Closed')
                self.closed = True
        self.set_verbosity(15)
        self.set_option('allow takeovers', True)
        self.connect_server([Fake_Restarter] + [self.Disconnector] * 6)
    def test_start_bot_blocking(self):
        ''' Bot-starting cares about the IP address someone connects from.'''
        def lazy_admin(self, line, *args):
            from language import ADM
            self.queue = []
            self.send(ADM(self.name)(str(line) % args))
            sleep(15)
            return [msg.fold()[2][0] for msg in self.queue if msg[0] is ADM]
        self.connect_server([])
        self.Fake_Master.admin = lazy_admin
        master = self.connect_player(self.Fake_Master)
        self.connect_player(self.Fake_Player)
        master.admin('Server: become master')
        self.assertContains('Recruit more players first, or use your own bots.',
                master.admin('Server: start holdbot'))

class Network_Full_Games(NetworkTestCase):
    def change_option(self, name, value):
        config.option_class.local_opts.update({name: value})
    def connect_server(self, *args):
        from functions import any
        ServerTestCase.connect_server(self, *args)
        while not self.server.closed:
            while any(not game.closed for game in self.server.games if game):
                sleep(3)
                self.server.check()
            self.server.check_close()
    def test_holdbots(self):
        ''' Seven drawing holdbots'''
        from player import HoldBot
        self.connect_server([HoldBot] * 7)
    def test_one_dumbbot(self):
        ''' Six drawing holdbots and a dumbbot'''
        from player  import HoldBot
        from dumbbot import DumbBot
        self.set_verbosity(1)
        DumbBot.verbosity = 20
        self.connect_server([DumbBot, HoldBot, HoldBot,
                HoldBot, HoldBot, HoldBot, HoldBot])
    def test_dumbbots(self):
        ''' seven dumbbots, quick game'''
        from dumbbot import DumbBot
        self.connect_server([DumbBot] * 7)
    def test_two_games(self):
        ''' seven holdbots; two games'''
        self.set_verbosity(4)
        from player import HoldBot
        self.connect_server([HoldBot] * 7, 2)
        self.failUnlessEqual(len(self.server.games), 2)
    def test_evilbots(self):
        ''' Six drawing evilbots and a holdbot'''
        from player  import HoldBot
        from evilbot import EvilBot
        self.set_verbosity(4)
        #self.change_option('move time limit', 10)
        #self.change_option('validate incoming messages', False)
        #self.change_option('publish individual orders', True)
        self.connect_server([HoldBot, EvilBot, EvilBot,
                EvilBot, EvilBot, EvilBot, EvilBot])

if __name__ == '__main__': unittest.main()
