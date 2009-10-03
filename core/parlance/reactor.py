r'''Parlance Twisted reactor core
    Copyright (C) 2009  Eric Wald
    
    This module uses Twisted as an asynchronous engine.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

from twisted.application.reactors import getReactorTypes, installReactor
from twisted.internet.interfaces import IHalfCloseableProtocol
from twisted.internet.protocol import ClientFactory
from twisted.internet.stdio import StandardIO
from twisted.protocols.basic import LineOnlyReceiver
from zope.interface import implements

from parlance.config import VerboseObject
from parlance.util import expand_list


class AsyncManager(VerboseObject):
    r'''Manages four types of clients: polled, timed, threaded, and dynamic.
        
        Each type of client must have a close() method and corresponding
        closed property.  A client will be removed if it closes itself;
        otherwise, it will be closed when the ThreadManager closes.
        
        Each client must also have a prefix property, which should be a
        string, and a run() method, which is called as described below.
        
        Polled clients have a fileno(), which indicates a file descriptor.
        The client's run() method is called whenever that file descriptor
        has input to process.  In addition, the client is closed when its
        file descriptor runs out of input.  Each file descriptor can only
        support one polled client.
        
        The run() method of a timed client is called after the amount of
        time specified when it is registered.  The specified delay is a
        minimum, not an absolute; polled clients take precedence.
        
        Dynamic clients are like timed clients, but have a time_left() method
        to specify when to call the run() method.  The time_left() method is
        called each time through the polling loop, and should return either
        a number of seconds (floating point is permissible) or None.
        
        The run() method of a threaded client is called immediately in
        a separate thread.  The manager will wait for all threads started
        in this way, during its close() method.
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
    
    def add_polled(self, client):
        self.log_debug(11, 'New polled client: %s', client.prefix)
        assert not self.closed
        fd = client.fileno()
        self.polled[fd] = client
        if self.polling: self.polling.register(fd, self.flags)
    def add_input(self, input_handler, close_handler):
        r'''Adds a client listening to standard input.
            May be extra slow on some platforms.
        '''#'''
        
        # Magic: We need to keep a reference to this object.
        self.stdin = StandardIO(self.InputWaiter(input_handler, close_handler))
    def add_timed(self, client, delay):
        self.log_debug(11, 'New timed client: %s', client.prefix)
        assert not self.closed
        deadline = time() + delay
        self.timed.append((deadline, client))
        return deadline
    def add_dynamic(self, client):
        self.log.debug("New dynamic client: %s", client.prefix)
        assert not self.closed
        self.dynamic.append(client)
    
    def add_threaded(self, client):
        self.log.debug("New threaded client: %s", client.prefix)
        assert not self.closed
        return self.new_thread(client.run)
    def new_thread(self, target, *args, **kwargs):
        return self.reactor.callInThread(target, *args, **kwargs)
    
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
