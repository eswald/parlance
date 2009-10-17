r'''Test cases for Parlance network activity
    Copyright (C) 2004-2009  Eric Wald
    
    This module includes functional (end-to-end) test cases to verify that the
    whole system works together; unfortunately, many of them can take quite
    a while to run, and a few need bots that can actually finish a game.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

import socket
import sys
import unittest
from itertools       import count
from struct          import pack
from time            import time, sleep

from twisted.internet.protocol import ClientFactory

from parlance.config    import VerboseObject
from parlance.fallbacks import any
from parlance.gameboard import Variant
from parlance.language  import Representation, Token, protocol
from parlance.reactor   import ThreadManager
from parlance.network   import DaideClientProtocol, DaideFactory, DaideProtocol
from parlance.player    import Clock, HoldBot
from parlance.server    import Server
from parlance.tokens    import ADM, BRA, HLO, IAM, KET, NME, REJ, YES

from parlance.test.server import ServerTestCase

class FakeManager(ThreadManager):
    def install(self):
        import twisted.internet.reactor
        return twisted.internet.reactor
    def process(self, time_limit=5, wait_time=1):
        r'''Run a single iteration of the reactor.'''
        if not self.reactor.running:
            # Yes, this is officially discouraged.
            self.reactor.startRunning()
        started = time()
        while time() - started < time_limit:
            self.reactor.iterate(wait_time)
    def close(self):
        # Don't stop the reactor; it shouldn't be running.
        self.closed = True

class NetworkTestCase(ServerTestCase):
    class Disconnector(ServerTestCase.Fake_Player):
        sleep_time = 14
        name = 'Loose connection'
        def handle_message(self, message):
            self.__super.handle_message(message)
            if message[0] is HLO:
                self.manager.add_timed(self, self.sleep_time)
            elif message[0] is REJ:
                raise UserWarning("Rejected command: " + str(message))
        def run(self):
            self.send(ADM(str(self.power))('Passcode: %d' % self.pcode))
            self.close()
    class FakeFactory(DaideFactory, ClientFactory):
        r'''A fake ClientFactory to test the netowrk protocols.'''
        
        def __init__(self, protocol):
            self.protocol = protocol
            self.client = None
            self.__super.__init__()
        
        def buildProtocol(self, addr):
            p = self.__super.buildProtocol(addr)
            self.client = p
            return p
    
    port = count(16714)
    
    def setUp(self):
        ServerTestCase.setUp(self)
        self.manager = FakeManager()
        self.manager.options.wait_time = 10
        self.manager.options.block_exceptions = False
    def connect_server(self, clients, games=1, poll=True, **kwargs):
        self.set_option('games', games)
        self.set_option('port', self.port.next())
        
        manager = self.manager
        self.server = server = Server(manager)
        sock = manager.add_server(server)
        if not sock:
            raise UserWarning("ServerSocket failed to open")
        if not poll: manager.polling = None
        
        for dummy in range(games):
            if server.closed: raise UserWarning('Server closed early')
            players = []
            for player_class in clients:
                player = manager.add_client(player_class, **kwargs)
                if not player:
                    raise UserWarning('Manager failed to start a client')
                players.append(player)
                manager.process()
            while any(not p.closed for p in players):
                manager.process(23)
        return sock
    def fake_client(self, protocol=DaideClientProtocol):
        self.factory = factory = self.FakeFactory(protocol)
        host = "localhost"
        port = factory.options.port
        self.manager.reactor.connectTCP(host, port, factory)
        return factory

class Network_Errors(NetworkTestCase):
    def assertLocalError(self, error, protocol, time_limit=5):
        self.connect_server([])
        self.fake_client(protocol)
        self.manager.process(time_limit)
        self.failUnlessEqual(self.factory.client.errors, [("Local", error)])
    def test_timeout(self):
        ''' Thirty-second timeout for the Initial Message'''
        self.failUnlessEqual(protocol.Timeout, 0x01)
        class TestingProtocol(DaideProtocol):
            def connectionMade(self):
                self.__super.connectionMade()
                self.errors = []
                self.first = (self.RM, self.proto.NotRMError)
            def log_error(self, faulty, code):
                self.errors.append((faulty, code))
        self.assertLocalError(protocol.Timeout, TestingProtocol, 35)
    def test_initial(self):
        ''' Client's first message must be Initial Message.'''
        self.failUnlessEqual(protocol.NotIMError, 0x02)
        class TestingProtocol(DaideProtocol):
            def connectionMade(self):
                self.__super.connectionMade()
                self.errors = []
                self.first = (self.RM, self.proto.NotRMError)
                self.send_dcsp(self.DM, '')
            def log_error(self, faulty, code):
                self.errors.append((faulty, code))
        self.assertLocalError(protocol.NotIMError, TestingProtocol)
    def test_endian(self):
        ''' Integers must be sent in network byte order.'''
        self.failUnlessEqual(protocol.EndianError, 0x03)
        class TestingProtocol(DaideProtocol):
            def connectionMade(self):
                self.__super.connectionMade()
                self.errors = []
                self.first = (self.RM, self.proto.NotRMError)
                self.send_dcsp(self.IM,
                    pack('<HH', protocol.version, protocol.magic))
            def log_error(self, faulty, code):
                self.errors.append((faulty, code))
        self.assertLocalError(protocol.EndianError, TestingProtocol)
    def test_endian_short(self):
        ''' Length must be sent in network byte order.'''
        self.failUnlessEqual(protocol.EndianError, 0x03)
        class TestingProtocol(DaideProtocol):
            def connectionMade(self):
                self.__super.connectionMade()
                self.errors = []
                self.first = (self.RM, self.proto.NotRMError)
                self.transport.write(pack('<BxHHH', self.IM, 4,
                        protocol.version, protocol.magic))
            def log_error(self, faulty, code):
                self.errors.append((faulty, code))
        self.assertLocalError(protocol.EndianError, TestingProtocol)
    def test_magic(self):
        ''' The magic number must match.'''
        self.failUnlessEqual(protocol.MagicError, 0x04)
        class TestingProtocol(DaideProtocol):
            def connectionMade(self):
                self.__super.connectionMade()
                self.errors = []
                self.first = (self.RM, self.proto.NotRMError)
                self.send_dcsp(self.IM,
                    pack('<HH', protocol.version, protocol.magic >> 1))
            def log_error(self, faulty, code):
                self.errors.append((faulty, code))
        self.assertLocalError(protocol.MagicError, TestingProtocol)
    def test_version(self):
        ''' The server must recognize the protocol version.'''
        self.failUnlessEqual(protocol.VersionError, 0x05)
        self.connect_server([])
        client = self.fake_client()
        client.send_dcsp(client.IM,
                pack('!HH', protocol.version + 1, protocol.magic))
        self.manager.process()
        self.failUnlessEqual(client.error_code, protocol.VersionError)
    def test_duplicate(self):
        ''' The client must not send more than one Initial Message.'''
        self.failUnlessEqual(protocol.DuplicateIMError, 0x06)
        self.connect_server([])
        client = self.fake_client()
        client.send_dcsp(client.IM,
                pack('!HH', protocol.version, protocol.magic))
        client.send_dcsp(client.IM,
                pack('!HH', protocol.version, protocol.magic))
        self.manager.process()
        self.failUnlessEqual(client.error_code, protocol.DuplicateIMError)
    def test_server_initial(self):
        ''' The server must not send an Initial Message.'''
        self.failUnlessEqual(protocol.ServerIMError, 0x07)
        # Todo
    def test_type(self):
        ''' Stick to the defined set of message types.'''
        self.failUnlessEqual(protocol.MessageTypeError, 0x08)
        self.connect_server([])
        client = self.fake_client()
        client.send_dcsp(client.IM,
                pack('!HH', protocol.version, protocol.magic))
        client.send_dcsp(10, '')
        self.manager.process()
        self.failUnlessEqual(client.error_code, protocol.MessageTypeError)
    def test_short(self):
        ''' Detect messages chopped in transit.'''
        self.failUnlessEqual(protocol.LengthError, 0x09)
        self.connect_server([])
        client = self.fake_client()
        client.send_dcsp(client.IM,
                pack('!HH', protocol.version, protocol.magic))
        client.sock.sendall(pack('!BxH', client.DM, 20) + HLO(0).pack())
        self.manager.process()
        self.failUnlessEqual(client.error_code, protocol.LengthError)
    def test_quick(self):
        ''' The client should not send a DM before receiving the RM.'''
        self.failUnlessEqual(protocol.EarlyDMError, 0x0A)
        # I don't see a way to trigger this with the current system.
    def test_representation(self):
        ''' The server's first message must be RM.'''
        self.failUnlessEqual(protocol.NotRMError, 0x0B)
        # Todo
    def test_unexpected(self):
        ''' The server must not send an unrequested RM.'''
        self.failUnlessEqual(protocol.UnexpectedRM, 0x0C)
        # Todo
    def test_client_representation(self):
        ''' The client must not send Representation Messages.'''
        self.failUnlessEqual(protocol.ClientRMError, 0x0D)
        self.connect_server([])
        client = self.fake_client()
        client.send_dcsp(client.IM,
                pack('!HH', protocol.version, protocol.magic))
        self.manager.process()
        client.send_RM()
        self.manager.process()
        self.failUnlessEqual(client.error_code, protocol.ClientRMError)
    def test_reserved_tokens(self):
        ''' "Reserved for AI use" tokens must never be sent over the wire.'''
        class ReservedSender(object):
            def __init__(self, **kwargs):
                self.closed = False
            def register(self, transport, representation):
                self.send = transport
                self.rep = representation
                self.send(Token('HMM', 0x585F)())
            def close(self): self.closed = True
        self.failUnlessEqual(protocol.IllegalToken, 0x0E)
        self.connect_server([])
        client = self.fake_client(ReservedSender)
        self.manager.process()
        self.failUnlessEqual(client.error_code, protocol.IllegalToken)

class Network_Basics(NetworkTestCase):
    def test_RM_unpacking(self):
        rep = Representation({
            0x4100: "ONE",
            0x4101: "TWO",
            0x4102: "TRE",
            0x5100: "AAA",
            0x5101: "BBB",
            0x5102: "CCC",
            0x5003: "DDD",
        }, protocol.base_rep)
        self.connect_server([])
        self.server.default_game().variant = Variant("testing", rep)
        
        client = self.fake_client()
        client.send_dcsp(client.IM,
            pack('!HH', protocol.version, protocol.magic))
        self.manager.process()
        self.failUnlessEqual(client.rep, rep)
    def test_full_connection(self):
        ''' Seven fake players, polling if possible'''
        self.connect_server([self.Disconnector] * 7)
    def test_without_poll(self):
        ''' Seven fake players, selecting'''
        self.connect_server([self.Disconnector] * 7, poll=False)
    def test_with_timer(self):
        ''' Seven fake players and an observer'''
        self.connect_server([Clock] + ([self.Disconnector] * 7))
    def test_takeover(self):
        ''' Takeover ability after game start'''
        success = []
        
        class Fake_Takeover(VerboseObject):
            ''' A false player, who takes over a position and then quits.'''
            sleep_time = 7
            name = 'Impolite Finisher'
            def __init__(self, power, passcode, manager=None):
                self.__super.__init__()
                self.log_debug(9, 'Fake player started')
                self.restarted = False
                self.closed = False
                self.power = power
                self.passcode = passcode
                self.manager = manager
            def connect(self):
                return self.manager.create_connection(self)
            def register(self, transport, representation):
                self.send = transport
                self.rep = representation
                self.send(NME(self.power.text)(str(self.passcode)))
            def close(self):
                self.log_debug(9, 'Closed')
                self.closed = True
            def handle_message(self, message):
                self.log_debug(5, '<< %s', message)
                if message[0] is YES and message[2] is IAM:
                    success.append(self)
                    self.send(ADM(self.power.text)('Takeover successful'))
                    sleep(self.sleep_time)
                    self.close()
                elif message[0] is REJ and message[2] is NME:
                    self.send(IAM(self.power)(self.passcode))
                elif message[0] is ADM: pass
                else:
                    raise AssertionError('Unexpected message: ' + str(message))
        class Fake_Restarter(self.Disconnector):
            ''' A false player, who starts Fake_Takeover after receiving HLO.'''
            sleep_time = 3
            def close(self):
                self.manager.add_client(Fake_Takeover, power=self.power,
                    passcode=self.pcode)
                self.log_debug(9, 'Closed')
                self.closed = True
        self.set_option('takeovers', True)
        self.connect_server([Fake_Restarter] + [self.Disconnector] * 6)
        self.assertEqual(len(success), 1)
        self.assertEqual(success[0].__class__, Fake_Takeover)
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
    def test_unpack_message(self):
        rep = Representation({0x4101: 'Sth'}, protocol.base_rep)
        msg = [HLO.number, BRA.number, 0x4101, KET.number]
        unpacked = rep.unpack_message(pack('!HHHH', *msg))
        self.failUnlessEqual(repr(unpacked),
            "Message([HLO, [Token('Sth', 0x4101)]])")
    def test_game_port(self):
        # Each game can be accessed on its own port, if so configured.
        self.connect_server([])
        
        game_port = self.port.next()
        self.set_option('game_port_min', game_port)
        self.set_option('game_port_max', game_port)
        middle = self.server.start_game()
        
        self.set_option('game_port_min', None)
        self.set_option('game_port_max', None)
        default = self.server.start_game()
        player = self.connect_player(self.Fake_Player)
        self.failUnlessEqual(player.game_id, default.game_id)
        
        self.set_option('port', game_port)
        player = self.connect_player(self.Fake_Player)
        self.failUnlessEqual(player.game_id, middle.game_id)

class Network_Full_Games(NetworkTestCase):
    def test_holdbots(self):
        ''' Seven drawing holdbots'''
        self.connect_server([HoldBot] * 7)
    def test_two_games(self):
        ''' seven holdbots; two games'''
        self.connect_server([HoldBot] * 7, 2)
        self.failUnlessEqual(len(self.server.games), 2)

if __name__ == '__main__': unittest.main()
