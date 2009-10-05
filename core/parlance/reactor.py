r'''Parlance Twisted reactor core
    Copyright (C) 2009  Eric Wald
    
    This module uses Twisted as an asynchronous engine.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

from time import time

from twisted.application.reactors import getReactorTypes, installReactor
from twisted.internet.interfaces import IHalfCloseableProtocol
from twisted.internet.protocol import ClientFactory
from twisted.internet.stdio import StandardIO
from twisted.protocols.basic import LineOnlyReceiver
from twisted.web.error import NoResource
from twisted.web.resource import Resource
from twisted.web.server import Site
from zope.interface import implements

from parlance.config import VerboseObject
from parlance.util import expand_list


class AsyncManager(VerboseObject):
    r'''Thin layer over Twisted's reactor, for historical reasons.
    '''#'''
    
    __options__ = (
        ("reactor", str, 'select', None,
            "Which Twisted reactor to install.",
            "Choose from %s." % expand_list(sorted(installer.shortName
                for installer in getReactorTypes()), "or")),
        ('host', str, '', None,
            'The name or IP address of the server.',
            'If blank, the server will listen on all possible addresses,',
            'and clients will connect to localhost.'),
        ('port', int, 16713, None,
            'The port that the server listens on.'),
    )
    
    def __init__(self):
        self.closed = False
        self.__super.__init__()
        self.reactor = installReactor(self.options.reactor)
    
    def run(self):
        ''' The main loop; never returns until the manager closes.'''
        self.log.debug('Main loop started')
        self.reactor.run()
    def process(self, wait_time=1):
        r'''Run a single iteration of the reactor.
            Meant for testing only; be sure to run close() afterward.
        '''#"""#'''
        if not self.reactor.running:
            self.reactor.callWhenRunning(self.reactor.crash)
            self.reactor.run()
        self.reactor.iterate(wait_time)
    def close(self):
        self.closed = True
        self.reactor.stop()
    
    def add_input(self, input_handler, close_handler):
        r'''Adds a client listening to standard input.
            May be extra slow on some platforms.
        '''#'''
        
        # Magic: We need to keep a reference to this object.
        self.stdin = StandardIO(self.InputWaiter(input_handler, close_handler))
    def add_timed(self, client, delay):
        self.log.debug('New timed client: %s', client.prefix)
        assert not self.closed
        return self.reactor.callLater(delay, client.run)
    def add_dynamic(self, client):
        # Use add_timed() or something like TimeoutMixin instead.
        # Call reset() on the result whenever the value changes.
        self.log.debug("New dynamic client: %s", client.prefix)
        assert not self.closed
        now = time()
        delay = client.time_left()
        if delay is not None:
            return self.add_timed(client, delay)
    
    def add_threaded(self, client):
        self.log.debug("New threaded client: %s", client.prefix)
        assert not self.closed
        return self.new_thread(client.run)
    def new_thread(self, target, *args, **kwargs):
        return self.reactor.callInThread(target, *args, **kwargs)
    
    # Help for specific types of clients
    def add_server(self, server, game=None):
        # Todo: Merge this with create_connection?
        name = server.prefix
        socket = ServerSocket(self, server, game)
        result = socket.open()
        if result:
            self.add_polled(socket)
            self.log.debug("Opened a connection for %s", name)
        else: self.log.warn("Failed to open a connection for %s", socket)
        return result and socket
    def add_server(self, server, game=None):
        factory = DaideServerFactory(server)
        self.reactor.listenTCP(self.options.port, factory)
        self.reactor.run()
    def add_client(self, player_class, **kwargs):
        # Now calls player.connect(), in case the player wants to use
        # a separate process or something.
        player = player_class(manager=self, **kwargs)
        return player.connect()
    def create_connection(self, player):
        host = self.options.host
        port = self.options.port
        return self.reactor.connectTCP(host, port, DaideClientFactory())
    
    class InputWaiter(LineOnlyReceiver):
        r'''Protocol to direct stdin lines to the input handler.'''
        implements(IHalfCloseableProtocol)
        
        def __init__(self, input_handler, close_handler):
            self.input_handler = input_handler
            self.close_handler = close_handler
        
        def lineReceived(self, line):
            r'''New line from stdin.
                Pass it on to the caller.
            '''#"""#'''
            self.input_handler(line)
        
        def readConnectionLost():
            r'''Standard input has closed.
            '''#"""#'''
            self.close_handler()
        
        def writeConnectionLost():
            r'''Standard output has closed.
                Nothing important needs to be done here.
            '''#"""#'''

class DaideClientFactory(VerboseObject, ClientFactory):
    # ReconnectingClientFactory might be useful,
    # but clients won't always want to reconnect.
    
    def __init__(self, player):
        self.__super.__init__()
        self.player = player
    
    def buildProtocol(self, addr):
        self.resetDelay()
        return DaideClientProtocol()
    
    def clientConnectionLost(self, connector, reason):
        self.log.debug("Connection lost: %s", reason)
        if self.player.reconnect():
            connector.connect()
    
    def clientConnectionFailed(self, connector, reason):
        self.log.debug("Connection failed: %s", reason)
        if self.player.reconnect():
            connector.connect()

class DaideServerFactory(Site):
    protocol = DaideServerProtocol
    
    class Nothing(Resource):
        def getChild(self, name, request):
            return NoResource()
    
    def __init__(self, server):
        Site.__init__(self, self.Nothing())
