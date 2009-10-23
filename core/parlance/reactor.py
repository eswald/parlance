r'''Parlance Twisted reactor core
    Copyright (C) 2009  Eric Wald
    
    This module uses Twisted as an asynchronous engine.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

from time import time

from twisted.application.reactors import getReactorTypes, installReactor
from twisted.internet.interfaces import IHalfCloseableProtocol
from twisted.internet.stdio import StandardIO
from twisted.protocols.basic import LineOnlyReceiver
from zope.interface import implements

from parlance.config import VerboseObject
from parlance.util import expand_list


class ThreadManager(VerboseObject):
    r'''Thin layer over Twisted's reactor, for historical reasons.
    '''#'''
    
    __options__ = (
        ("reactor", str, "select", None,
            "Which Twisted reactor to install.",
            "Choose from %s." % expand_list(sorted(installer.shortName
                for installer in getReactorTypes()), "or")),
    )
    
    def __init__(self, reactor=None):
        self.closed = False
        self.__super.__init__()
        self.reactor = reactor or self.install()
        self.running = []
    def install(self):
        installReactor(self.options.reactor)
        import twisted.internet.reactor
        return twisted.internet.reactor
    
    def run(self):
        ''' The main loop; never returns until the manager closes.'''
        self.log.debug('Main loop started')
        self.reactor.run()
    def close(self):
        self.closed = True
        self.reactor.stop()
    def check(self):
        self.log.debug("Checking for stopped clients")
        self.running = [p for p in self.running if not p.closed]
        if not (self.running or self.closed):
            self.close()
    
    def add_input(self, input_handler, close_handler):
        r'''Adds a client listening to standard input.
            May be extra slow on some platforms.
        '''#'''
        
        # Magic: We need to keep a reference to this object.
        self.stdin = StandardIO(InputWaiter(input_handler, close_handler))
    def add_timed(self, client, delay):
        self.log.debug('New timed client: %s', client.prefix)
        assert not self.closed
        return self.reactor.callLater(delay, client.run)
    
    def add_threaded(self, client):
        self.log.debug("New threaded client: %s", client.prefix)
        assert not self.closed
        return self.new_thread(client.run)
    def new_thread(self, target, *args, **kwargs):
        return self.reactor.callInThread(target, *args, **kwargs)
    
    # Help for specific types of clients
    def add_server(self, server, game=None):
        # This import can't be done before the reactor is installed.
        from parlance.network import DaideServerFactory
        factory = DaideServerFactory(server, game)
        port = factory.openPort(self.reactor)
        self.running.append(server)
        return port and factory
    def add_client(self, player_class, **kwargs):
        # Now calls player.connect(), in case the player wants to use
        # a separate process or something.
        player = player_class(manager=self, **kwargs)
        self.running.append(player)
        return player.connect() and player
    def create_connection(self, player):
        # This import can't be done before the reactor is installed.
        from parlance.network import DaideClientFactory
        factory = DaideClientFactory(player)
        host = factory.options.host
        port = factory.options.port
        return self.reactor.connectTCP(host, port, factory)

class InputWaiter(LineOnlyReceiver):
    r'''Protocol to direct stdin lines to the input handler.'''
    implements(IHalfCloseableProtocol)
    delimiter = '\n'
    
    def __init__(self, input_handler, close_handler):
        self.input_handler = input_handler
        self.close_handler = close_handler
    
    def lineReceived(self, line):
        r'''New line from stdin.
            Pass it on to the caller.
        '''#"""#'''
        self.input_handler(line)
    
    def readConnectionLost(self):
        r'''Standard input has closed.
        '''#"""#'''
        self.close_handler()
    
    def writeConnectionLost(self):
        r'''Standard output has closed.
            Nothing important needs to be done here.
        '''#"""#'''
