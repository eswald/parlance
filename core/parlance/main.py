r'''Parlance command-line interface
    Copyright (C) 2004-2009  Eric Wald
    
    This module includes functions to run players or the server based on
    command-line arguments.  It also includes the threading engine used by the
    back ends of each.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

import select
from itertools import chain
from os.path   import basename
from sys       import argv, exit, stdin
from time      import sleep, time

try: from threading import Thread, Lock
except ImportError:
    Thread = None
    from dummy_threading import Lock

from config    import Configuration, VerboseObject, variants
from fallbacks import any
from language  import protocol
from network   import Client, ServerSocket

__all__ = [
    'ThreadManager',
    'Program',
    'ClientProgram',
    'ServerProgram',
]

# Public methods:
# - add_client(class, **kwargs)             parang.evolve, parlance.test.network, parlance.server, parlance.main, pariah.aiserver
# - add_dynamic(client)                     parlance.server
# - add_input(handle_input, handle_close)   parang.chatty, parlance.main
# - add_polled(client)                      parlance.test.network, parlance.main, parlance.network
# - add_timed(function, seconds)            parang.blabberbot, parlance.test.network, parlance.network
# - add_threaded(client)                    parang.chatty
# - close()                                 parang.evolve, parlance.server, parlance.main, parlance.network, pariah.aiserver
# - closed                                  parang.evolve, parlance.test.server, parlance.server, parlance.main, parlance.network
# - new_thread(target, *args)               parlance.player
# - process(seconds)                        parang.evolve, parlance.test.server, parlance.test.network, pariah.aiserver
# - run()                                   parlance.main
# - options.wait_time                       parlance.test.network
# - options.block_exceptions                pariah.aiserver, parang.evolve, parlance.test.network

class ThreadManager(VerboseObject):
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
    flags = (getattr(select, 'POLLIN', 0) |
            getattr(select, 'POLLERR', 0) |
            getattr(select, 'POLLHUP', 0) |
            getattr(select, 'POLLNVAL', 0))
    
    __options__ = (
        ('wait_time', int, 600, 'idle timeout for server loop',
            'Default time (in seconds) to wait for select() or poll() system calls.',
            'Not used when any client or game has a time limit.',
            'Higher numbers waste less CPU time, up to a point,',
            'but may make the program less responsive to certain inputs.'),
        ('sleep_time', int, 1, 'idle timeout for busy loops',
            'Default time (in seconds) to sleep in potential busy loops.',
            'Higher numbers may waste less CPU time in certain situations,',
            'but will make the program less responsive to certain inputs.'),
        ('block_exceptions', bool, True, None,
            'Whether to block exceptions seen by the ThreadManager.',
            'When on, the program is more robust, but harder to debug.'),
    )
    
    def __init__(self):
        self.__super.__init__()
        self.log_debug(10, 'Attempting to create a poll object')
        if self.flags:
            try: self.polling = select.poll()
            except: self.polling = None
        else: self.polling = None
        
        self.polled = {}        # fd -> client
        self.timed = []         # (time, client)
        self.threaded = []      # (thread, client)
        self.dynamic = []       # client
        self.closed = False
    def clients(self):
        return [item[1] for item in chain(self.polled.iteritems(),
                self.timed, self.threaded)] + self.dynamic
    
    def run(self):
        ''' The main loop; never returns until the manager closes.'''
        self.log_debug(10, 'Main loop started')
        try:
            while not self.closed:
                if self.clients():
                    self.process(self.options.wait_time)
                    if self.polled or self.timed or self.closed:
                        pass
                    else:
                        # Avoid turning this into a busy loop
                        self.log_debug(7, 'sleep()ing for %.3f seconds',
                                self.options.sleep_time)
                        sleep(self.options.sleep_time)
                else: self.close()
            self.log_debug(11, 'Main loop ended')
        except KeyboardInterrupt:
            self.log_debug(7, 'Interrupted by user')
        except:
            self.log_debug(1, 'Error in main loop; closing')
            self.close()
            raise
        self.close()
    def process(self, wait_time=1):
        ''' Runs as long as there is something productive to do.'''
        method = self.polling and self.poll or self.select
        while not self.closed:
            timeout = self.get_timeout()
            result = False
            if self.polled:
                poll_time = (timeout is None) and wait_time or timeout
                self.log_debug(7, '%s()ing for %.3f seconds',
                        method.__name__, poll_time)
                result = method(poll_time)
            elif timeout:
                self.log_debug(7, 'sleep()ing for %.3f seconds', timeout)
                sleep(timeout)
            if not result:
                if timeout is None: break
                if self.timed: self.check_timed()
                if self.dynamic: self.check_dynamic()
        if self.threaded: self.clean_threaded()
    def attempt(self, client):
        self.log_debug(12, 'Running %s', client.prefix)
        try: client.run()
        except KeyboardInterrupt:
            self.log_debug(7, 'Interrupted by user')
            self.close()
        except Exception, e:
            self.log_debug(1, 'Exception running %s: %s %s',
                    client.prefix, e.__class__.__name__, e.args)
            if not client.closed: client.close()
            if not self.options.block_exceptions: raise
    def close(self):
        self.closed = True
        if self.threaded: self.clean_threaded()
        for client in self.clients():
            if not client.closed: client.close()
        self.wait_threads()
    
    # Polled client handling
    class InputWaiter(VerboseObject):
        ''' File descriptor for waiting on standard input.'''
        def __init__(self, input_handler, close_handler):
            self.__super.__init__()
            self.handle_input = input_handler
            self.handle_close = close_handler
            self.closed = False
        def fileno(self): return stdin.fileno()
        def run(self):
            line = ''
            try: line = raw_input()
            except EOFError: self.close()
            if line: self.handle_input(line)
        def close(self):
            self.closed = True
            self.handle_close()
    def add_polled(self, client):
        self.log_debug(11, 'New polled client: %s', client.prefix)
        assert not self.closed
        fd = client.fileno()
        self.polled[fd] = client
        if self.polling: self.polling.register(fd, self.flags)
    def remove_polled(self, fd):
        # Warning: Must be called in the same thread as the polling.
        # Outside of this class, call the client's close() method instead.
        self.log_debug(11, 'Removing polled client: %s',
                self.polled.pop(fd).prefix)
        if self.polling: self.polling.unregister(fd)
    def add_input(self, input_handler, close_handler):
        ''' Adds a polled client listening to standard input.
            On Windows, adds it as a threaded client instead;
            because select() can't handle non-socket file descriptors.
        '''#'''
        waiter = self.InputWaiter(input_handler, close_handler)
        if self.polling: self.add_polled(waiter)
        else: self.add_looped(waiter)
    def select(self, timeout):
        self.clean_polled()
        try: ready = select.select(self.polled.values(), [], [], timeout)[0]
        except select.error, e:
            self.log_debug(7, 'Select error received: %s', e.args)
            # Bad file descriptors should be caught in the next pass.
            if e.args[0] != 9:
                self.close()
                raise
        else:
            if ready:
                for client in ready:
                    self.attempt(client)
            else: return False
        return True
    def poll(self, timeout):
        self.clean_polled()
        try: ready = self.polling.poll(timeout * 1000)
        except select.error, e:
            self.log_debug(7, 'Polling error received: %s', e.args)
            # Ignore interrupted system calls
            if e.args[0] != 4:
                self.close()
                raise
        else:
            if ready:
                for fd, event in ready:
                    self.check_polled(fd, event)
            else: return False
        return True
    def check_polled(self, fd, event):
        client = self.polled[fd]
        self.log_debug(15, 'Event %s received for %s', event, client.prefix)
        if event & select.POLLIN:
            self.attempt(client)
        if client.closed:
            self.log_debug(7, '%s closed itself', client.prefix)
            self.remove_polled(fd)
        elif event & (select.POLLERR | select.POLLHUP):
            self.log_debug(7, 'Event %s received for %s', event, client.prefix)
            self.remove_polled(fd)
            if not client.closed: client.close()
        elif event & select.POLLNVAL:
            self.log_debug(7, 'Invalid fd for %s', client.prefix)
            self.remove_polled(fd)
            if not client.closed: client.close()
    def clean_polled(self):
        # Warning: This doesn't catch closed players until their Clients close.
        for fd, client in self.polled.items():
            if client.closed: self.remove_polled(fd)
    
    # Timed client handling
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
    def get_timeout(self):
        now = time()
        times = [t for t in (client.time_left(now)
                for client in self.dynamic if not client.closed)
                if t is not None]
        when = [t for t,c in self.timed if not c.closed]
        if when: times.append(0.005 + min(when) - now)
        if times: result = max(0, min(times))
        else: result = None
        return result
    def check_timed(self):
        self.log_debug(14, 'Checking timed clients')
        now = time()
        timed = self.timed
        self.timed = []
        for deadline, client in timed:
            if client.closed:
                self.log_debug(11, 'Removing timed client: %s', client.prefix)
                continue
            if deadline < now: self.attempt(client)
            else: self.timed.append((deadline, client))
    def check_dynamic(self):
        self.log_debug(14, 'Checking dynamic clients')
        now = time()
        removals = []
        for client in self.dynamic:
            if client.closed:
                self.log_debug(11, 'Removing dynamic client: %s', client.prefix)
                removals.append(client)
            elif None is not client.time_left(now) <= 0: self.attempt(client)
        for client in removals: self.dynamic.remove(client)
    
    # Threaded client handling
    class LoopClient(object):
        def __init__(self, client):
            self.client = client
            self.closed = False
        def run(self):
            while not (self.closed or self.client.closed):
                self.client.run()
            self.close()
        def close(self):
            self.closed = True
            if not self.client.close: self.client.close()
        @property
        def prefix(self): return self.client.prefix
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
    def add_looped(self, client):
        self.add_threaded(self.LoopClient(client))
    def new_thread(self, target, *args, **kwargs):
        self.add_threaded(self.ThreadClient(target, *args, **kwargs))
    def wait_threads(self):
        for thread, client in self.threaded:
            while thread.isAlive():
                try: thread.join(self.options.sleep_time)
                except KeyboardInterrupt:
                    if not client.closed: client.close()
                    print 'Still waiting for threads...'
    def clean_threaded(self):
        self.log_debug(14, 'Checking threaded clients')
        self.threaded = [item for item in self.threaded if item[0].isAlive()]
    
    # Help for specific types of clients
    def add_server(self, server, game=None):
        # Todo: Merge this with create_connection?
        name = server.prefix
        socket = ServerSocket(self, server, game)
        result = socket.open()
        if result:
            self.add_polled(socket)
            self.log.debug("Opened a connection for %s", name)
        else: self.log.warn("Failed to open a connection for %s", name)
        return result and socket
    def add_client(self, player_class, **kwargs):
        # Now calls player.connect(), in case the player wants to use
        # a separate process or something.
        player = player_class(manager=self, **kwargs)
        return player.connect()
    def create_connection(self, player):
        name = player.prefix
        client = Client(player)
        result = client.open()
        if result:
            self.add_polled(client)
            self.log.debug('Opened a connection for ' + name)
        else: self.log.warn('Failed to open a connection for ' + name)
        return result and client

class Program(VerboseObject):
    r'''A command-line program that can also be instantiated other ways.
        Accepts configuration options as arguments.
    '''#"""#'''
    
    @staticmethod
    def help_requested():
        signals = "--help", "-h", "-?", "/?", "/h"
        return any(flag in argv for flag in signals)
    
    @staticmethod
    def progname():
        return basename(argv[0])
    
    @classmethod
    def usage(cls, problem=None, *args):
        print "Usage: %s [OPTIONS]" % cls.progname()
        if problem: print str(problem) % args
        exit(1)
    
    @classmethod
    def main(cls):
        if cls.help_requested():
            cls.usage()
        cls.run_program(Configuration.arguments)
    
    @classmethod
    def run_program(cls, args):
        raise NotImplementedError

class ClientProgram(Program):
    # Command-line program
    allow_multiple = False
    allow_country = False
    
    @classmethod
    def usage(cls, problem=None, *args):
        name = cls.__name__
        if cls.allow_multiple:
            print ('Usage: %s [host][:port] [number]%s [-v<level>]' %
                (cls.progname(), cls.allow_country and ' [power=passcode] ...' or ''))
            print 'Connects <number> copies of %s to <host>:<port>' % name
        else:
            print 'Usage: %s [host][:port]%s -v<level>' % (cls.progname(),
                    cls.allow_country and ' [power=passcode]' or '')
            print 'Connects a copy of %s to <host>:<port>' % name
        if problem: print str(problem) % args
        exit(1)
    
    @classmethod
    def run_program(cls, args):
        r'''Run one or more Parlance clients.
            Takes options from the command line, including special syntax for
            host, port, number of bots, and passcodes.
        '''#'''
        name = cls.__name__
        num = None
        countries = {}
        
        host = Configuration._args.get('host')
        for arg in args:
            if arg.isdigit():
                if not cls.allow_multiple:
                    cls.usage('%s does not support multiple copies.', name)
                elif num is None:
                    num = int(arg)
                else: cls.usage()       # Only one number specification allowed
            elif len(arg) > 3 and arg[3] == '=':
                if cls.allow_country:
                    countries[arg[:3].upper()] = int(arg[4:])
                else: cls.usage('%s does not accept country codes.', name)
            elif host is None:
                Configuration.set_globally('host', arg)
            else: cls.usage()           # Only one host specification allowed
        if num is None: num = 1
        
        manager = ThreadManager()
        while num > 0 or countries:
            num -= 1
            if countries:
                nation, pcode = countries.popitem()
                result = manager.add_client(cls, power=nation, passcode=pcode)
            else: result = manager.add_client(cls)
            if not result:
                manager.log.critical('Failed to start %s.  Sorry.', name)
        manager.run()
    
    def connect(self):
        r'''Start a network connection.'''
        return self.manager.create_connection(self)

class ServerProgram(Program):
    @classmethod
    def usage(cls, problem=None, *args):
        print 'Usage: %s [-gGAMES] [-vLEVEL] [VARIANT]' % cls.progname()
        print 'Serves GAMES games of VARIANT, with output verbosity LEVEL'
        if problem: print str(problem) % args
        exit(1)
    
    @classmethod
    def run_program(cls, args):
        r'''Run a game server.
            Takes options from the command line, including number of games and the
            default map.
        '''#'''
        opts = {}
        if args:
            if args[0] in variants:
                Configuration.set_globally('variant', args[0])
            else: cls.usage('Unknown variant %r', args[0])
        
        manager = ThreadManager()
        server = cls(manager)
        if manager.add_server(server):
            manager.run()
        else: manager.log.critical("Failed to open the socket.")

class RawClient(ClientProgram):
    r'''Simple client to translate DM to and from text.
        The client will take messages in token syntax from standard input and
        send them to the server, printing any received messages to standard
        output in the same syntax.
    '''#'''
    
    prefix = 'RawClient'
    def __init__(self, manager):
        self.transport = None  # A function that accepts messages
        self.rep       = None  # The representation message
        self.closed    = False # Whether the connection has ended, or should end
        self.manager   = manager
    def register(self, transport, representation):
        print 'Connected.'
        self.transport = transport
        self.rep = representation
        self.manager.add_input(self.handle_input, self.close)
    def handle_message(self, message):
        ''' Process a new message from the server.'''
        print '>>', message
    def close(self):
        ''' Informs the player that the connection has closed.'''
        print 'Closed.'
        self.closed = True
        if not self.manager.closed: self.manager.close()
    def handle_input(self, line):
        try: message = self.rep.translate(line)
        except Exception, err: print str(err) or '??'
        else: self.send(message)
    def send(self, message):
        if self.transport and not self.closed:
            self.transport(message)

class RawServer(ServerProgram):
    r'''Simple server to translate DM to and from text.
        The server will take messages in token syntax from standard input and
        send them to each connected client, printing any received messages to
        standard output in the same syntax.  The server will close when the
        last client disconnects.
    '''#'''
    
    class FakeGame(object):
        def __init__(self, server):
            self.variant = server
            self.game_id = 'ID'
        def disconnect(self, client):
            print 'Client #%d has disconnected.' % client.client_id
    def __init__(self, thread_manager):
        self.closed = False
        self.manager = thread_manager
        self.clients = {}
        self.rep = protocol.default_rep
        self.game = self.FakeGame(self)
        thread_manager.add_input(self.handle_input, self.close)
        print 'Waiting for connections...'
    def handle_message(self, client, message):
        ''' Process a new message from the client.'''
        print '#%d >> %s' % (client.client_id, message)
    def close(self):
        ''' Informs the user that the connection has closed.'''
        self.closed = True
        if not self.manager.closed: self.manager.close()
    def add_client(self, client):
        self.clients[client.client_id] = client
    def disconnect(self, client):
        del self.clients[client.client_id]
        if not self.clients: self.close()
    def handle_input(self, line):
        try:
            message = self.rep.translate(line)
        except Exception, err:
            print str(err) or '??'
        else:
            for client in self.clients.values():
                client.write(message)
    def broadcast_admin(self, text): pass
    def default_game(self, game_id=None):
        return self.game
