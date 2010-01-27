r'''Test cases for Parlance network and timing activity
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

from mock import Mock, patch
from twisted.internet.protocol import ClientFactory, ServerFactory
from twisted.protocols.basic import LineOnlyReceiver

from parlance.config    import VerboseObject
from parlance.fallbacks import any
from parlance.gameboard import Variant
from parlance.language  import Representation, Token, protocol
from parlance.reactor   import ThreadManager
from parlance.network   import DaideClientProtocol, DaideFactory, DaideProtocol
from parlance.player    import Clock, HoldBot, Player
from parlance.server    import Server
from parlance.tokens    import ADM, BRA, CCD, DRW, HLO, IAM, KET, NME, REJ, YES
from parlance.xtended   import standard

from parlance.test import fails
from parlance.test.server import ServerTestCase, test_variants

class FakeManager(ThreadManager):
    def install(self):
        import twisted.internet.reactor
        from twisted.python import log
        
        self.__err = None
        def err(_stuff=None, *args, **kwargs):
            # Let Nose know about any errors that occur.
            if _stuff is None:
                raise
            else:
                self.__err = _stuff
        log.err = err
        return twisted.internet.reactor
    def process(self, time_limit=5, wait_time=1):
        r'''Run the reactor for a limited time.'''
        if not self.reactor.running:
            # Yes, this is officially discouraged.
            self.reactor.startRunning()
        started = time()
        while time() - started < time_limit:
            self.reactor.iterate(wait_time)
            self.log.debug("%s seconds left in iteration",
                max(0, time_limit - (time() - started)))
            if self.__err:
                raise self.__err
    def close(self):
        # Don't stop the reactor; it shouldn't be running.
        # However, do process it to flush out anything in the pipe.
        self.process(1)
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
        r'''A fake ClientFactory to test the network protocols.'''
        
        def __init__(self, protocol):
            self.protocol = protocol
            self.client = None
            self.player = Mock()
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
        self.set_option('port', self.port.next())
    def connect_server(self):
        manager = self.manager
        self.server = server = Server(manager)
        sock = manager.add_server(server)
        if not sock:
            raise UserWarning("ServerSocket failed to open")
        return server
    def run_game(self, clients, games=1, **kwargs):
        self.set_option('games', games)
        server = self.connect_server()
        manager = self.manager
        
        for dummy in range(games):
            if server.closed: raise UserWarning('Server closed early')
            game = server.default_game()
            players = []
            for player_class in clients:
                player = manager.add_client(player_class, **kwargs)
                if not player:
                    raise UserWarning('Manager failed to start a client')
                players.append(player)
                manager.process(.2)
            while any(not p.closed for p in players):
                manager.process(2)
        return game
    def fake_client(self, protocol=DaideClientProtocol):
        self.factory = factory = self.FakeFactory(protocol)
        host = "localhost"
        port = factory.options.port
        self.manager.reactor.connectTCP(host, port, factory)
        return factory

class Network_Errors(NetworkTestCase):
    def assertLocalError(self, error, initial, time_limit=5):
        self.server = Mock()
        self.server.default_game().variant = standard
        self.manager.add_server(self.server)
        
        class TestingProtocol(DaideProtocol):
            def connectionMade(self):
                self.__super.connectionMade()
                self.errors = []
                self.first = (self.RM, self.proto.NotRMError)
                initial(self)
            def send_IM(self):
                self.send_dcsp(self.IM,
                    pack('!HH', self.proto.version, self.proto.magic))
            def log_error(self, faulty, code):
                self.errors.append((faulty, code))
        
        self.fake_client(TestingProtocol)
        self.manager.process(time_limit)
        self.failUnlessEqual(self.factory.client.errors, [("Local", error)])
    
    def test_timeout(self):
        ''' Thirty-second timeout for the Initial Message'''
        self.failUnlessEqual(protocol.Timeout, 0x01)
        def initial(client): pass
        self.assertLocalError(protocol.Timeout, initial, 35)
    def test_initial(self):
        ''' Client's first message must be Initial Message.'''
        self.failUnlessEqual(protocol.NotIMError, 0x02)
        def initial(client): client.send_dcsp(client.DM, '')
        self.assertLocalError(protocol.NotIMError, initial)
    def test_endian(self):
        ''' Integers must be sent in network byte order.'''
        self.failUnlessEqual(protocol.EndianError, 0x03)
        def initial(client):
            client.send_dcsp(client.IM,
                pack('<HH', protocol.version, protocol.magic))
        self.assertLocalError(protocol.EndianError, initial)
    def test_endian_short(self):
        ''' Length must be sent in network byte order.'''
        self.failUnlessEqual(protocol.EndianError, 0x03)
        def initial(client):
            client.transport.write(pack('<BxHHH', client.IM, 4,
                    protocol.version, protocol.magic))
        self.assertLocalError(protocol.EndianError, initial)
    def test_magic(self):
        ''' The magic number must match.'''
        self.failUnlessEqual(protocol.MagicError, 0x04)
        def initial(client):
            client.send_dcsp(client.IM,
                pack('!HH', protocol.version, protocol.magic >> 1))
        self.assertLocalError(protocol.MagicError, initial)
    def test_version(self):
        ''' The server must recognize the protocol version.'''
        self.failUnlessEqual(protocol.VersionError, 0x05)
        def initial(client):
            client.send_dcsp(client.IM,
                pack('!HH', protocol.version + 5, protocol.magic))
        self.assertLocalError(protocol.VersionError, initial)
    def test_duplicate(self):
        ''' The client must not send more than one Initial Message.'''
        self.failUnlessEqual(protocol.DuplicateIMError, 0x06)
        def initial(client):
            client.send_IM()
            client.send_IM()
        self.assertLocalError(protocol.DuplicateIMError, initial)
    def test_server_initial(self):
        ''' The server must not send an Initial Message.'''
        self.failUnlessEqual(protocol.ServerIMError, 0x07)
        # Todo
    def test_type(self):
        ''' Stick to the defined set of message types.'''
        self.failUnlessEqual(protocol.MessageTypeError, 0x08)
        def initial(client):
            client.send_IM()
            client.send_dcsp(10, "")
        self.assertLocalError(protocol.MessageTypeError, initial)
    def test_short(self):
        ''' Detect messages chopped in transit.'''
        self.failUnlessEqual(protocol.LengthError, 0x09)
        def initial(client):
            client.send_IM()
            client.transport.write(pack('!BxH', client.DM, 20) + HLO(0).pack())
        self.assertLocalError(protocol.LengthError, initial, 35)
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
        def initial(client):
            client.send_IM()
            client.send_RM(standard.rep)
        self.assertLocalError(protocol.ClientRMError, initial)
    def test_reserved_tokens(self):
        ''' "Reserved for AI use" tokens must never be sent over the wire.'''
        self.failUnlessEqual(protocol.IllegalToken, 0x0E)
        def initial(client):
            client.send_IM()
            client.write(Token('HMM', 0x585F)())
        self.assertLocalError(protocol.IllegalToken, initial)

class Network_Basics(NetworkTestCase):
    def test_RM_unpacking(self):
        variant = test_variants["mini"]
        server = Mock()
        server.default_game().variant = variant
        self.manager.add_server(server)
        case = self
        
        class TestingProtocol(DaideClientProtocol):
            def connectionMade(self):
                case.client = self
                self.__super.connectionMade()
        
        self.fake_client(TestingProtocol)
        self.manager.process()
        self.failUnlessEqual(self.client.rep, variant.rep)
    def test_takeover(self):
        ''' Takeover ability after game start'''
        success = []
        class Fake_Takeover(VerboseObject):
            ''' A false player, who takes over a position and then quits.'''
            name = 'Impolite Finisher'
            def __init__(self, power, passcode, manager=None):
                self.__super.__init__()
                self.log_debug(9, 'Fake player started')
                self.closed = False
                self.power = power
                self.passcode = passcode
                self.manager = manager
            def connect(self):
                return self.manager.create_connection(self)
            def reconnect(self):
                return False
            def register(self, transport, representation):
                self.transport = transport
                self.rep = representation
                self.send(NME(self.power.text)(str(self.passcode)))
            def send(self, msg):
                self.transport.write(msg)
            def close(self):
                self.log_debug(9, 'Closed')
                self.closed = True
            def handle_message(self, message):
                self.log_debug(5, '<< %s', message)
                if message[0] is YES and message[2] is IAM:
                    success.append(self)
                    self.send(ADM(self.power.text)('Takeover successful'))
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
        self.run_game([Fake_Restarter] + [self.Disconnector] * 6)
        self.assertEqual(len(success), 1)
        self.assertEqual(success[0].__class__, Fake_Takeover)
        # Todo: Check the name change on the server's side.
    def test_start_bot_blocking(self):
        ''' Bot-starting cares about the IP address someone connects from.'''
        self.connect_server()
        master = self.connect_player(self.Fake_Master)
        self.connect_player(self.Fake_Player)
        self.manager.process()
        self.assertContains('Recruit more players first, or use your own bots.',
                master.admin('Server: start holdbot'))
    def test_unpack_message(self):
        rep = Representation({0x4101: 'Sth'}, protocol.base_rep)
        msg = [HLO.number, BRA.number, 0x4101, KET.number]
        unpacked = rep.unpack(pack('!HHHH', *msg))
        self.failUnlessEqual(repr(unpacked),
            "Message([HLO, [Token('Sth', 0x4101)]])")
    def test_game_port(self):
        # Each game can be accessed on its own port, if so configured.
        server = self.connect_server()
        
        game_port = self.port.next()
        self.set_option('game_port_min', game_port)
        self.set_option('game_port_max', game_port)
        middle = server.start_game()
        self.failUnlessEqual(middle.port.port, game_port)
        
        self.set_option('game_port_min', None)
        self.set_option('game_port_max', None)
        default = server.start_game()
        default_player = self.connect_player(self.Fake_Player)
        self.manager.process()
        self.failUnlessEqual(default_player.game_id, default.game_id)
        self.failUnlessEqual(default.port, None)
        
        self.set_option('port', game_port)
        player = self.connect_player(self.Fake_Player)
        self.manager.process()
        self.failUnlessEqual(player.game_id, middle.game_id)
        
        # Closing a game leaves clients on its port open.
        middle.close()
        self.manager.process()
        player.admin("Ping.")
        self.manager.process()
        self.failUnlessEqual(player.closed, False)
        player.close()
        self.manager.process()
        self.failUnlessEqual(middle.port.closed, True)
        
        # But new clients can't connect to that port.
        player = self.connect_player(self.Fake_Player)
        self.manager.process()
        self.failUnlessEqual(player.transport, None)
        self.failUnlessEqual(player.failures, 1)
    def test_disconnection(self):
        # The server should notice when a player disconnects.
        self.set_option('quit', False)
        server = self.connect_server()
        game = server.default_game()
        players = []
        while len(players) < 10 and not game.started:
            player = self.connect_player(self.Fake_Player)
            players.append(player)
            self.manager.process(1)
        self.assertEqual(game.started, True)
        players[2].queue = []
        player.close()
        self.manager.process(1)
        self.assertContains(CCD (player.power), players[2].queue)

class TimingCases(NetworkTestCase):
    def start_game(self, time_limit):
        # There are more precautions here than usual,
        # because failure can lead to an infinite loop.
        self.set_option('MTL', time_limit)
        server = self.connect_server()
        self.game = game = server.default_game()
        players = []
        while len(players) < 10 and not game.started:
            player = self.connect_player(self.Fake_Player)
            players.append(player)
            self.manager.process(1)
        self.assertEqual(game.started, True)
        return players
    
    def test_turn_timeout(self):
        # The turn runs when the time limit expires.
        self.start_game(6)
        start = self.game.judge.turn()
        self.manager.process(4)
        self.assertEqual(self.game.judge.turn(), start)
        self.manager.process(4)
        self.assertNotEqual(self.game.judge.turn(), start)
    def test_turn_ready(self):
        # The turn runs when all orders are in.
        players = self.start_game(20)
        start = self.game.judge.turn()
        for player in players:
            player.hold_all()
        self.manager.process(2)
        self.assertNotEqual(self.game.judge.turn(), start)
    @fails
    def test_drawn_early(self):
        # The turn runs when all players agree on a draw.
        players = self.start_game(20)
        for player in players:
            player.send(+DRW)
        self.manager.process(2)
        self.assertEqual(self.game.judge.game_result, +DRW)

class DppTestCase(NetworkTestCase):
    def connect(self, delim="\r\n"):
        class TestingProtocol(VerboseObject, LineOnlyReceiver):
            delimiter = delim
            def connectionMade(self):
                self.__super.connectionMade()
                self.lines = []
                self.sendLine("DPP/0.17")
            def lineReceived(self, line):
                self.lines.append(line)
        
        self.set_option("squeeze_parens", True)
        self.set_option("variant", "standard")
        self.connect_server()
        factory = self.fake_client(TestingProtocol)
        self.manager.process(1)
        return factory.client
    
    def test_windows_endings(self):
        # The server should detect and send Windows-style line endings
        client = self.connect("\r\n")
        client.sendLine("OBS")
        self.manager.process(1)
        self.assertEqual(client.lines, ['YES (OBS)', 'MAP ("standard")'])
    
    def test_posix_endings(self):
        # The server should detect and send Unix-style line endings
        client = self.connect("\n")
        client.sendLine("OBS")
        self.manager.process(1)
        self.assertEqual(client.lines, ['YES (OBS)', 'MAP ("standard")'])
    
    def test_bad_message(self):
        # This message caused a significant problem.
        client = self.connect()
        client.sendLine("REJ")
        self.manager.process(1)
        self.assertEqual(client.lines, ["HUH (REJ ERR)"])

class Network_Full_Games(NetworkTestCase):
    def test_full_connection(self):
        # Seven fake players
        self.run_game([self.Disconnector] * 7)
    def test_with_timer(self):
        # Seven fake players and an observer
        self.run_game([Clock] + ([self.Disconnector] * 7))
    def test_holdbots(self):
        # Seven drawing holdbots
        game = self.run_game([HoldBot] * 7)
        self.assertEqual(game.judge.game_result, +DRW)
    def test_two_games(self):
        # seven holdbots; two games
        # Todo: Eliminate the race condition causing one bot to sometimes get
        # REJ (NME) from the server.
        game = self.run_game([HoldBot] * 7, 2)
        self.failUnlessEqual(len(self.server.games), 2)
        self.assertEqual(game.judge.game_result, +DRW)

if __name__ == '__main__': unittest.main()
