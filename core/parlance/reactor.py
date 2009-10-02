r'''Parlance Twisted reactor core
    Copyright (C) 2009  Eric Wald
    
    This module uses Twisted as an asynchronous engine.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

from twisted.application.reactors import getReactorTypes, installReactor
from twisted.internet.interfaces import IHalfCloseableProtocol
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
            "Available reactors: ", expand_list(installer.shortName
                for installer in getReactorTypes())),
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
        self.log_debug(11, 'New dynamic client: %s', client.prefix)
        assert not self.closed
        self.dynamic.append(client)
    def add_threaded(self, client):
        if Thread:
            self.log_debug(11, 'New threaded client: %s', client.prefix)
            assert not self.closed
            thread = Thread(target=self.attempt, args=(client,))
            thread.start()
            self.threaded.append((thread, client))
        else:
            self.log_debug(11, 'Emulating threaded client: %s', client.prefix)
            self.attempt(client)
    def add_client(self, player_class, **kwargs):
        name = player_class.__name__
        client = Client(player_class, manager=self, **kwargs)
        result = client.open()
        if result:
            self.add_polled(client)
            self.log_debug(10, 'Opened a Client for ' + name)
        else: self.log_debug(7, 'Failed to open a Client for ' + name)
        return result and client
    def new_thread(self, target, *args, **kwargs):
        self.add_threaded(self.ThreadClient(target, *args, **kwargs))
    
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
    class ThreadClient(object):
        def __init__(self, target, *args, **kwargs):
            self.target = target
            self.args = args
            self.kwargs = kwargs
            self.closed = False
            arguments = chain((repr(arg) for arg in args),
                    ("%s=%r" % (name, value)
                        for name, value in kwargs.iteritems()))
            self.prefix = (target.__name__ + '(' +
                    str.join(', ', arguments) + ')')
        def run(self):
            self.target(*self.args, **self.kwargs)
            self.close()
        def close(self):
            self.closed = True
