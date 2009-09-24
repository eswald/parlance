r'''Parlance web framework
    Copyright (C) 2009  Eric Wald
    
    This module allows Parlance to report its settings to a web browser.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

from twisted.protocols.stateful import StatefulProtocol
from twisted.web.error import NoResource
from twisted.web.http import HTTPChannel
from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.internet import reactor

from calendar import calendar
from struct import pack, unpack
from parlance.language import Message, Representation, protocol

class DaideProtocol(StatefulProtocol):
    r'''Base methods for the DAIDE Client-Server Protocol.'''
    
    class options:
        echo_final = False
        null_rm = False
    
    def connectionMade(self):
        self.configure(protocol)
        self.final_sent = False
    def close(self, notified=False):
        if not self.final_sent:
            if self.options.echo_final or not notified:
                self.send_dcsp(self.FM, "")
            self.final_sent = True
        self.transport.loseConnection()
        
        # State: ignore all incoming messages
        return (self.read_closed, 4)
    
    def getInitialState(self):
        print "Initializing State"
        return (self.read_header, 4)
    def dataReceived(self, data):
        print "Processing", repr(data)
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
    
    def write_msg(self, message):
        self.send_dcsp(self.DM, message.pack())
    def send_dcsp(self, msg_type, data):
        r'''Sends a DCSP message to the client.
            msg_type must be an integer, one of the defined message types.
            data must be a packed binary string.
        '''#'''
        print "Sending %s: %r" % (msg_type, data)
        msg = pack('!BxH', msg_type, len(data)) + data
        self.transport.write(msg)
    
    def read_header(self, data):
        msg_type, msg_len = unpack('!BxH', data)
        print "Header", repr(data), msg_type, msg_len
        if self.first:
            first, err = self.first
            if msg_type not in (first, self.FM, self.EM):
                return self.send_error(err)
            self.first = None
        
        handler = self.handlers.get(msg_type)
        if handler:
            state = (handler, msg_len)
        else:
            state = self.send_error(self.proto.MessageTypeError)
        return state
    def read_closed(self, data):
        return None
    
    def read_IM(self, data):
        r'''Verifies the Initial Message from the client.'''
        if len(data) == 4:
            (version, magic) = unpack('!HH', data)
            if magic == self.proto.magic:
                if version == self.proto.version:
                    self.rep = self.proto.default_rep
                    self.send_RM()
                    state = (self.read_header, 4)
                else: state = self.send_error(self.proto.VersionError)
            elif unpack('<HH', data)[1] == self.proto.magic:
                state = self.send_error(self.proto.EndianError)
            else: state = self.send_error(self.proto.MagicError)
        else: state = self.send_error(self.proto.LengthError)
        
        self.handlers[self.IM] = self.duplicate_IM
        return state
    def duplicate_IM(self, data):
        self.send_error(self.proto.DuplicateIMError)
    
    def send_RM(self):
        ''' Sends the representation message to the client.
            This implementation can be configured to always sends a full RM,
            or to rely on the default for the Standard map.
        '''#'''
        if self.options.null_rm and self.rep == self.proto.default_rep:
            data = ''
        else:
            data = str.join('', (pack('!H3sx', token.number, name)
                        for name, token in self.rep.items()))
        self.send_dcsp(self.RM, data)
    def read_RM(self, data):
        # This might check for UnexpectedRM, but that interferes with SEL.
        if len(data) % 6:
            state = self.send_error(self.proto.LengthError)
        else:
            self.read_representation(data)
            state = (self.read_header, 4)
        return state
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
            return self.send_error(self.proto.LengthError)
        elif not self.rep:
            return self.send_error(self.proto.EarlyDMError)
        else:
            msg = self.unpack_message(data)
            if msg:
                self.handle_message(msg)
                state = (self.read_header, 4)
            else:
                return self.send_error(self.proto.IllegalToken)
        return state
    def unpack_message(self, data):
        r'''Produces a Message from a string of token numbers.
            Uses values in the representation, if available.
        '''#'''
        try:
            msg = Message([self.rep[x]
                for x in unpack('!' + 'H'*(len(data)//2), data)])
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
        self.log_error("Client", code)
        self.send_dcsp(self.EM, pack('!H', code))
        return self.close(True)
    def read_EM(self, data):
        code = unpack('!H', data)[0]
        self.log_error("Server", code)
        return self.close(True)
    def log_error(self, faulty, code):
        text = self.proto.error_strings.get(code, "Unknown")
        #self.log_debug(8, '%s error 0x%02X (%s)', faulty, code, text)
    
    def read_FM(self, data):
        return self.close(True)

class DaideClientProtocol(DaideProtocol):
    def connectionMade(self):
        DaideProtocol.connectionMade(self)
        self.first = (self.RM, self.proto.NotRMError)
        self.send_dcsp(self.IM, pack('!HH',
            self.proto.version, self.proto.magic))
        self.player = None
    
    def read_IM(self, data):
        self.send_error(self.proto.ServerIMError)
    
    def read_RM(self, data):
        state = DaideProtocol.read_RM(data)
        # Todo: Create and register the player
        #self.player = self.pclass(send_method=self.send,
        #    representation=self.rep, **self.kwargs)
        #self.player.register()
        self.player = self.factory.create_player()
        return state
    
    def handle_message(self, msg):
        self.player.handle_message(msg)
        if self.player.closed:
            self.close()

class DaideServerProtocol(DaideProtocol, HTTPChannel):
    # - DaideServerProtocol
    #   - DaideProtocol
    #     - StatefulProtocol
    #       - Protocol
    #         - BaseProtocol
    #   - HTTPChannel
    #     - LineReceiver
    #       - Protocol
    #         - BaseProtocol
    #       - _PauseableMixin
    #     - TimeoutMixin
    
    def connectionMade(self):
        DaideProtocol.connectionMade(self)
        self.first = (self.IM, self.proto.NotIMError)
        self.setTimeout(30)
        self.__buffer = ""
    
    def switchProtocol(self, proto, timeout):
        print "Switching to ", proto
        data = self.__buffer
        del self.__buffer
        self.dataReceived = lambda msg: proto.dataReceived(self, msg)
        proto.connectionMade(self)
        self.dataReceived(data)
        self.setTimeout(timeout)
    
    def dataReceived(self, data):
        r'''Switch to a new protocol as soon as possible.'''
        if self.__buffer:
            data = self.__buffer + data
        self.__buffer = data
        print "Received", repr(data)
        
        if len(data) >= 4:
            if "\0" in data:
                # Binary data; use DCSP
                self.switchProtocol(DaideProtocol, None)
                self.transport.setTcpKeepAlive(True)
            else:
                # Probably text; switch to HTTP
                self.switchProtocol(HTTPChannel, self.site.timeOut)
    
    def read_RM(self, data):
        self.send_error(self.proto.ClientRMError)
    
    def handle_message(self, msg):
        print msg

class YearPage(Resource):
    r'''From Jean-Paul Calderone's "Twisted Web in 60 seconds" tutorial.'''
    def __init__(self, year):
        Resource.__init__(self)
        self.year = year
    
    def render_GET(self, request):
        return "<html><body><pre>%s</pre></body></html>" % (calendar(self.year),)

class Calendar(Resource):
    def getChild(self, name, request):
        try:
            year = int(name)
        except ValueError:
            return NoResource()
        else:
            return YearPage(year)

root = Calendar()
factory = Site(root)
factory.protocol = DaideServerProtocol
reactor.listenTCP(8880, factory)
reactor.run()
