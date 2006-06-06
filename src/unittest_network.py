''' Unit tests for the PyDip network module
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
'''#'''

import socket
import unittest
from struct import pack
from time import sleep

import config
import network
from main import ThreadManager
from functions import any, Verbose_Object
from language import Token, ADM, HLO, IAM, NME, REJ, YES
from server import Server
from unittest_server import ServerTestCase

class NetworkTestCase(ServerTestCase):
    class Disconnector(ServerTestCase.Fake_Player):
        sleep_time = 14
        name = 'Loose connection'
        def handle_message(self, message):
            self.__super.handle_message(message)
            if message[0] is HLO:
                self.manager.add_timed(self, self.sleep_time)
        def run(self):
            self.send(ADM(str(self.power))('Passcode: %d' % self.pcode))
            self.close()
    class FakeClient(network.Client):
        ''' A fake Client to test the server timeout.'''
        is_server = False
        prefix = 'Fake Client'
        error_code = None
        
        def open(self):
            # Open the socket
            self.sock = sock = socket.socket()
            sock.connect((self.opts.host or 'localhost', self.opts.port))
            sock.settimeout(None)
            
            # Required by the DCSP document
            try: sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            except: self.log_debug(7, 'Could not set SO_KEEPALIVE')
            
            if self.pclass:
                # Send initial message
                self.log_debug(9, 'Sending Initial Message')
                self.send_dcsp(self.IM, pack('!HH', self.proto.version, self.proto.magic));
            
            return True
        def send_error(self, code, from_them=False):
            if from_them: self.error_code = code
            self.__super.send_error(code, from_them)
    
    def setUp(self):
        ServerTestCase.setUp(self)
        self.manager = ThreadManager()
        self.manager.wait_time = 10
        self.manager.pass_exceptions = True
    def connect_server(self, clients, games=1, poll=True, **kwargs):
        config.option_class.local_opts.update({'number of games' : games})
        manager = self.manager
        sock = network.ServerSocket(Server, manager)
        if not poll: sock.polling = None
        if sock.open():
            self.server = server = sock.server
        else: raise UserWarning('ServerSocket failed to open')
        if not server: raise UserWarning('ServerSocket lacks a server')
        manager.add_polled(sock)
        for dummy in range(games):
            if server.closed: raise UserWarning('Server closed early')
            players = []
            for player_class in clients:
                player = manager.add_client(player_class, **kwargs)
                if not player:
                    raise UserWarning('Manager failed to start a client')
                players.append(player)
            while any(not p.closed for p in players):
                manager.process(23)
    def fake_client(self, player_class):
        name = player_class and player_class.__name__ or str(player_class)
        client = self.FakeClient(player_class)
        result = client.open()
        if result: self.manager.add_polled(client)
        else: raise UserWarning('Failed to open a Client for ' + name)
        return result and client
    def set_verbosity(self, level):
        super(NetworkTestCase, self).set_verbosity(level)
        if network.Connection.verbosity >= 7:
            network.Connection.verbosity = 6

class Network_Basics(NetworkTestCase):
    def test_timeout(self):
        ''' Thirty-second timeout for the Initial Message'''
        self.connect_server([])
        client = self.fake_client(None)
        self.manager.process()
        self.failUnlessEqual(client.error_code, client.opts.Timeout)
    def test_reserved_tokens(self):
        ''' "Reserved for AI use" tokens must never be sent over the wire.'''
        class ReservedSender(object):
            def __init__(self, send_method, **kwargs):
                self.send = send_method
                self.closed = False
            def register(self):
                self.send(Token('HMM', 0x585F)())
            def close(self): self.closed = True
        self.connect_server([])
        client = self.fake_client(ReservedSender)
        self.manager.process()
        self.failUnlessEqual(client.error_code, client.opts.IllegalToken)
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
            name = 'Impolite Finisher'
            def __init__(self, send_method, representation,
                    power, passcode, manager=None):
                self.log_debug(9, 'Fake player started')
                self.restarted = False
                self.closed = False
                self.send = send_method
                self.rep = representation
                self.power = power
                self.passcode = passcode
            def register(self):
                self.send(NME(self.power.text)(str(self.passcode)))
            def close(self):
                self.log_debug(9, 'Closed')
                self.closed = True
            def handle_message(self, message):
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
                self.manager.add_client(Fake_Takeover, power=self.power,
                    passcode=self.pcode)
                self.log_debug(9, 'Closed')
                self.closed = True
        self.set_verbosity(15)
        self.set_option('allow takeovers', True)
        self.connect_server([Fake_Restarter] + [self.Disconnector] * 6)
    def test_start_bot_blocking(self):
        ''' Bot-starting cares about the IP address someone connects from.'''
        manager = self.manager
        def lazy_admin(self, line, *args):
            self.queue = []
            self.send(ADM(self.name)(str(line) % args))
            manager.process()
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
        self.set_verbosity(1)
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
