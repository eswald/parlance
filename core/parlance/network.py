r'''Parlance client/server communications
    Copyright (C) 2004-2009  Eric Wald
    
    This module includes classes to send and receive network messages, using
    the Pythonic messages for the interface to other parts of the program.
    This should be the only module that cares about details of the
    client-server protocol.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

from itertools import count
from struct import pack, unpack
from time import sleep

from twisted.internet.protocol import ClientFactory, connectionDone
from twisted.internet.error import CannotListenError
from twisted.protocols.basic import LineReceiver
from twisted.protocols.policies import TimeoutMixin
from twisted.protocols.stateful import StatefulProtocol
from twisted.web.error import NoResource
from twisted.web.http import HTTPChannel
from twisted.web.resource import Resource
from twisted.web.server import Site

from parlance.config import VerboseObject
from parlance.fallbacks import any, partial
from parlance.language import Message, Representation, protocol
from parlance.tokens import ADM, MDF, OFF, REJ, YES
from parlance.util import random_cycle

class DaideProtocol(VerboseObject, StatefulProtocol, TimeoutMixin):
    r'''Base methods for the DAIDE Client-Server Protocol.'''
    
    __options__ = (
        ('echo_final', bool, False, 'send unnecessary final messages',
            'Whether to send FM after receiving EM or FM.',
            'The extra FM may be useful to terminate input loops,',
            'particularly when using threads, but the protocol prohibits it.'),
        ('null_rm', bool, False, 'send empty representation messages',
            'Whether to send an empty RM for the standard map.',
            'The standard says yes, but that may be changed soon.'),
    )
    
    def connectionMade(self):
        self.configure(protocol)
        self.final_sent = False
        self.closed = False
    def close(self, notified=False):
        self.log.debug("Closing")
        self.closed = True
        self.setTimeout(None)
        if not self.final_sent:
            if self.options.echo_final or not notified:
                self.send_dcsp(self.FM, "")
            self.final_sent = True
        self.transport.loseConnection()
    
    def getInitialState(self):
        self.log.debug("Initializing State")
        return (self.read_header, 4)
    def dataReceived(self, data):
        #self.log.debug("Processing %r", data)
        StatefulProtocol.dataReceived(self, data)
    
    def configure(self, proto):
        self.send_final = True
        self.proto = proto
        self.rep = None
        
        # IM, DM, FM, etc.
        self.handlers = {}
        for name, value in proto.message_types.iteritems():
            abbr = name[0] + 'M'
            setattr(self, abbr, value)
            self.handlers[value] = getattr(self, "read_" + abbr)
    
    def write(self, message):
        self.send_dcsp(self.DM, message.pack())
    def send_dcsp(self, msg_type, data):
        r'''Sends a DCSP message to the client.
            msg_type must be an integer, one of the defined message types.
            data must be a packed binary string.
        '''#'''
        #self.log.debug("Sending %s: %r", msg_type, data)
        msg = pack('!BxH', msg_type, len(data)) + data
        self.transport.write(msg)
    
    def read_header(self, data):
        msg_type, msg_len = unpack('!BxH', data)
        #self.log.debug("Header %d/%d: %r", msg_type, msg_len, data)
        error = None
        if self.first:
            first, err = self.first
            if msg_type not in (first, self.FM, self.EM):
                error = err
            elif msg_type == self.IM and msg_len == 0x0400:
                error = self.proto.EndianError
            self.first = None
        
        if error is None:
            try:
                self.__handler = self.handlers[msg_type]
            except KeyError:
                error = self.proto.MessageTypeError
        
        if error is None:
            self.setTimeout(30)
            state = (self.read_body, msg_len)
        else:
            self.send_error(error)
            state = (self.read_closed, 4)
        
        return state
    def read_body(self, data):
        # Handles timeouts and state transitions for the handlers
        #self.log.debug("%s(%r)", self.__handler.__name__, data)
        self.setTimeout(None)
        self.__handler(data)
        if self.closed:
            state = (self.read_closed, 4)
        else:
            state = (self.read_header, 4)
        return state
    def read_closed(self, data):
        return None
    
    def read_IM(self, data):
        r'''Verifies the Initial Message from the client.'''
        if len(data) == 4:
            (version, magic) = unpack('!HH', data)
            if magic == self.proto.magic:
                if version == self.proto.version:
                    # Success!
                    self.service = Service(self, self.addr,
                        self.factory.server, self.factory.game)
                else: self.send_error(self.proto.VersionError)
            elif unpack('<HH', data)[1] == self.proto.magic:
                self.send_error(self.proto.EndianError)
            else: self.send_error(self.proto.MagicError)
        else: self.send_error(self.proto.LengthError)
        
        self.handlers[self.IM] = self.duplicate_IM
    def duplicate_IM(self, data):
        self.send_error(self.proto.DuplicateIMError)
    
    def send_RM(self, representation):
        ''' Sends the representation message to the client.
            This implementation can be configured to always sends a full RM,
            or to rely on the default for the Standard map.
        '''#'''
        if representation == self.rep:
            # No need to send again.
            return
        
        self.rep = representation
        if self.options.null_rm and representation == self.proto.default_rep:
            data = ''
        else:
            data = str.join('', (pack('!H3sx', token.number, name)
                        for name, token in representation.items()))
        self.send_dcsp(self.RM, data)
    def read_RM(self, data):
        # This might check for UnexpectedRM, but that interferes with SEL.
        if len(data) % 6:
            self.send_error(self.proto.LengthError)
        else:
            self.read_representation(data)
    def read_representation(self, data):
        ''' Creates a representation dictionary from the RM.
            This dictionary maps names to numbers and vice-versa.
        '''#'''
        if data:
            rep = {}
            fieldlen = 6
            for i in xrange(0, len(data), fieldlen):
                num, name = unpack('!H3sx', data[i:i+fieldlen])
                rep[num] = name
            self.rep = Representation(rep, self.proto.base_rep)
        else: self.rep = self.proto.default_rep
    
    def read_DM(self, data):
        if len(data) % 2 or not data:
            self.send_error(self.proto.LengthError)
        elif not self.rep:
            self.send_error(self.proto.EarlyDMError)
        else:
            msg = self.unpack_message(data)
            if msg:
                self.handle_message(msg)
            else:
                self.send_error(self.proto.IllegalToken)
    def unpack_message(self, data):
        r'''Produces a Message from a string of token numbers.
            Uses values in the representation, if available.
        '''#'''
        try:
            msg = self.rep.unpack(data)
        except ValueError:
            # Someone foolishly chose to disconnect over an unknown token.
            msg = None
        else:
            # Tokens in the "Reserved for AI use" category
            # must never be sent over the wire.
            if any('Reserved' in token.category_name() for token in msg):
                msg = None
        return msg
    def handle_message(self, msg):
        raise NotImplementedError
    
    def send_error(self, code):
        self.log_error("Foreign", code)
        self.send_dcsp(self.EM, pack('!H', code))
        self.close(True)
    def read_EM(self, data):
        code = unpack('!H', data)[0]
        self.log_error("Local", code)
        self.close(True)
    def log_error(self, faulty, code):
        text = self.proto.error_strings.get(code, "Unknown")
        self.log.error("%s error 0x%02X (%s)", faulty, code, text)
    def timeoutConnection(self):
        self.send_error(self.proto.LengthError)
    
    def read_FM(self, data):
        self.close(True)

class DaideClientProtocol(DaideProtocol):
    def connectionMade(self):
        DaideProtocol.connectionMade(self)
        self.first = (self.RM, self.proto.NotRMError)
        self.send_dcsp(self.IM, pack('!HH',
            self.proto.version, self.proto.magic))
    
    def read_IM(self, data):
        self.send_error(self.proto.ServerIMError)
    
    def read_RM(self, data):
        self.__super.read_RM(data)
        self.factory.player.register(self, self.rep)
    
    def handle_message(self, msg):
        player = self.factory.player
        player.handle_message(msg)
        if player.closed:
            self.close()

class DppProtocol(LineReceiver):
    r'''Line-based Diplomacy Programming Protocol.
        Like the Daide protocol, but using text instead of tokens.
    '''#"""#'''
    
    # This protocol could use LineOnlyReceiver,
    # but would then be incompatible with HTTPChannel.
    
    def connectionMade(self):
        self.configure(protocol)
        self.service = None
        
        # This detects both \n and \r\n for the first line.
        # We can auto-detect from that what to send.
        # Macintosh is just out of luck.
        self.delimiter = "\n"
    
    def close(self):
        self.log.debug("Closing")
        self.closed = True
    
    def lineReceived(self, line):
        if line.startswith("DPP/") and not self.service:
            if line.endswith("\r"):
                self.delimiter = "\r\n"
            self.service = Service(self, self.addr,
                self.factory.server, self.factory.game)
        else:
            self.translate(line)
    
    def translate(self, line):
        try:
            message = self.rep.translate(line)
        except Exception, err:
            response = str(err) or '??'
            self.sendLine(response)
        else:
            self.handle_message(message)
    
    def send_RM(self, representation):
        self.rep = representation
    
    def write(self, message):
        self.sendLine(str(message))
    
    def handle_message(self, msg):
        raise NotImplementedError

class DaideServerProtocol(DaideProtocol, DppProtocol, HTTPChannel):
    # - DaideServerProtocol
    #   - DaideProtocol
    #     - VerboseObject
    #       - Configurable
    #         - object
    #     - StatefulProtocol
    #       - Protocol
    #         - BaseProtocol
    #     - TimeoutMixin
    #   - DppProtocol
    #     - LineReceiver
    #       - Protocol
    #         - BaseProtocol
    #   - HTTPChannel
    #     - LineReceiver
    #       - Protocol
    #         - BaseProtocol
    #       - _PauseableMixin
    #     - TimeoutMixin
    
    def __init__(self):
        DaideProtocol.__init__(self)
        HTTPChannel.__init__(self)
        self.service = None
    
    def connectionMade(self):
        DaideProtocol.connectionMade(self)
        self.first = (self.IM, self.proto.NotIMError)
        self.setTimeout(30)
        self.__buffer = ""
    
    def connectionLost(self, reason=connectionDone):
        if self.service and not self.service.closed:
            self.service.close()
    
    def switchProtocol(self, proto, timeout):
        self.log.debug("Switching to %s", proto)
        # Do not wait until after connectionMade to reset the timeout,
        # because it might set a timeout of its own.
        self.setTimeout(timeout)
        data = self.__buffer
        del self.__buffer
        switching = [
            "dataReceived",
            "timeoutConnection",
            "lineReceived",
            "send_RM",
            "write",
            "close",
        ]
        
        for name in switching:
            handler = getattr(proto, name, None)
            setattr(self, name, handler and partial(handler, self))
        
        proto.connectionMade(self)
        self.dataReceived(data)
    
    def dataReceived(self, data):
        r'''Switch to a new protocol as soon as possible.'''
        if self.__buffer:
            data = self.__buffer + data
        self.__buffer = data
        self.log.debug("Received %r", data)
        
        if len(data) >= 4:
            if "\0" in data:
                # Binary data; use DCSP
                self.switchProtocol(DaideProtocol, None)
                self.transport.setTcpKeepAlive(True)
            elif data.startswith("DPP/"):
                self.switchProtocol(DppProtocol, None)
                self.transport.setTcpKeepAlive(True)
            else:
                # Probably text; switch to HTTP
                self.switchProtocol(HTTPChannel, self.site.timeOut)
    
    def read_RM(self, data):
        self.send_error(self.proto.ClientRMError)
    
    def handle_message(self, msg):
        self.log.debug("Handling %s", msg)
        self.service.handle_message(msg)
    
    def timeoutConnection(self):
        self.send_error(self.proto.Timeout)

class DaideFactory(VerboseObject):
    __options__ = (
        ('host', str, '', None,
            'The name or IP address of the server.',
            'If blank, the server will listen on all possible addresses,',
            'and clients will connect to localhost.'),
        ('port', int, 16713, None,
            'The port that the server listens on.'),
    )

class DaideClientFactory(DaideFactory, ClientFactory):
    # ReconnectingClientFactory might be useful,
    # but clients won't always want to reconnect.
    protocol = DaideClientProtocol
    
    def __init__(self, player):
        self.__super.__init__()
        self.player = player
    
    def clientConnectionLost(self, connector, reason):
        self.log.debug("Connection lost: %s", reason)
        if self.player.reconnect():
            connector.connect()
    
    def clientConnectionFailed(self, connector, reason):
        self.log.debug("Connection failed: %s", reason)
        if self.player.reconnect():
            connector.connect()

class DaideServerFactory(DaideFactory, Site):
    protocol = DaideServerProtocol
    
    __options__ = (
        ('game_port_min', int, None, None,
            'Minimum port for game-specific connections.',
            'If blank, no game-specific ports will be opened.'),
        ('game_port_max', int, None, None,
            'Maximum port for game-specific connections.',
            'If blank, no game-specific ports will be opened.'),
    )
    
    class Nothing(Resource):
        def getChild(self, name, request):
            return NoResource()
    
    class LogMixer(object):
        r'''Combines Parlance and Twisted logging facilities.
        '''#"""#'''
        def __init__(self, site):
            self.logger = site.log
            self.site = site
        def __call__(self, request):
            Site.log(self.site, request)
        def __getattr__(self, name):
            return getattr(self.logger, name)
    
    def __init__(self, server, game=None):
        DaideFactory.__init__(self)
        Site.__init__(self, self.Nothing())
        self.log = self.LogMixer(self)
        self.game = game
        self.server = server
        self.socket = None
        self.port = None
        self.closed = False
    def close(self):
        if self.socket:
            return self.socket.loseConnection().addCallback(self._socketClosed)
        else: self._socketClosed()
    def _socketClosed(self, value):
        self.closed = True
    
    def buildProtocol(self, addr):
        p = self.__super.buildProtocol(addr)
        p.addr = addr.host
        return p
    
    def openPort(self, reactor):
        if self.game:
            port = self.openGamePort(reactor,
                self.options.game_port_min,
                self.options.game_port_max)
        else:
            port = self.openMainPort(reactor, self.options.port)
        
        if port:
            self.closed = False
        self.port = port
        return port
    def openMainPort(self, reactor, port):
        wait_time = .125
        while wait_time < 10:
            if self.tryPort(reactor, port):
                break
            else:
                # Todo: Defer instead of sleeping?
                self.log.warn("Waiting for port %d", port)
                sleep(wait_time)
                wait_time *= 2
        else: port = None
        
        return port
    def openGamePort(self, reactor, start, end):
        if start and end:
            self.log_debug(11, "Checking ports %d-%d", start, end)
            for possible in random_cycle(start, end + 1):
                if self.tryPort(reactor, possible):
                    port = possible
                    break
            else: port = None
        else: port = None
        return port
    def tryPort(self, reactor, port):
        try:
            self.socket = reactor.listenTCP(port, self)
        except CannotListenError:
            self.socket = None
            return False
        return True

class Service(VerboseObject):
    r'''Connects a network player to the internal Server.'''
    next_id = count(1).next
    
    def __init__(self, connection, address, server, game_id=None):
        self.__super.__init__()
        self.sock      = connection
        self.client_id = self.next_id()
        self.address   = address
        self.country   = None
        self.name      = None
        self.version   = None
        self.guesses   = 0
        self.mastery   = False
        self.booted    = False
        self.server    = server
        self.errors    = 0
        self.game      = server.default_game(game_id)
        self.prefix    = 'Service #%d (%s)' % (self.client_id, game_id)
        self.closed    = False
        
        server.add_client(self)
        self.sock.send_RM(self.game.variant.rep)
    def power_name(self):
        return self.country and str(self.country) or ('#' + str(self.client_id))
    def full_name(self):
        return (self.name and ('%s (%s)' % (self.name, self.version))
                or 'An observer')
    def handle_message(self, msg):
        self.log_debug(4, '%3s >> %s', self.power_name(), msg)
        try: self.server.handle_message(self, msg)
        except Exception, e:
            self.log.exception('Error while handling "%s":', msg)
            self.server.broadcast_admin('An error has occurred.  '
                    'The server may be unreliable until it is restarted.')
            self.errors += 1
            if self.errors > 3:
                self.admin("You have caused too much trouble.  Good-bye.")
                self.boot()
            else: self.admin("Please don't do that again, whatever it was.")
    def close(self):
        self.log.debug("Closing.")
        if not self.closed:
            self.closed = True
            self.game.disconnect(self)
            self.server.disconnect(self)
            self.sock.close()
    def boot(self):
        ''' Forcibly disconnect a client, for misbehaving or being replaced.'''
        self.log_debug(6, 'Booting client #%d', self.client_id)
        self.booted = self.country
        self.country = None
        self.send(+OFF)
        self.close()
    def change_game(self, new_game):
        self.game.disconnect(self)
        self.game = new_game
        self.sock.send_RM(new_game.variant.rep)
        self.prefix = 'Service #%d (%s)' % (self.client_id, new_game.game_id)
    
    def write(self, message):
        # Skips the logging and watcher steps
        self.sock.write(message)
    def send(self, message):
        if message[0] is MDF:
            text = 'MDF [...]'
        else: text = unicode(message)
        self.log_debug(3, '%3s << %s', self.power_name(), text)
        self.write(message)
        for watcher in self.server.watchers:
            watcher.handle_server_message(message,
                self.game.game_id, self.client_id)
    def send_list(self, message_list):
        for msg in message_list:
            self.send(msg)
    def accept(self, message):
        self.send(YES(message))
    def reject(self, message):
        self.send(REJ(message))
    def admin(self, line, *args):
        self.send(ADM('Server')(unicode(line) % args))
