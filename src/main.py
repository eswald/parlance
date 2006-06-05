''' PyDip user interface (such as it is)
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
'''#'''

import select
from itertools import chain
from sys import argv
from time import sleep, time

try: from threading import Thread
except ImportError: Thread = None

import config
from functions import Verbose_Object

__all__ = [
    'ThreadManager',
    'run_player',
    'run_server',
]

class ThreadManager(Verbose_Object):
    ''' Manages four types of clients: polled, timed, threaded, and dynamic.
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
    try: flags = select.POLLIN | select.POLLERR | select.POLLHUP | select.POLLNVAL
    except AttributeError: flags = None
    
    def __init__(self):
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
        
        # Todo: Make these configurable
        self.autostart = []
        self.wait_time = 600
        self.sleep_time = 1
        self.pass_exceptions = False
    def clients(self):
        return [item[1] for item in chain(self.polled.iteritems(),
                self.timed, self.threaded)] + self.dynamic
    
    def run(self):
        ''' The main loop; never returns until the manager closes.'''
        self.log_debug(10, 'Main loop started')
        try:
            while not self.closed:
                if self.clients():
                    self.process(self.wait_time)
                    if not (self.polled or self.closed):
                        # Avoid turning this into a busy loop
                        self.log_debug(7, 'sleep()ing for %.3f seconds',
                                self.sleep_time)
                        sleep(self.sleep_time)
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
        self.clean_threaded()
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
            if self.pass_exceptions: raise
    def close(self):
        self.closed = True
        self.clean_threaded()
        for client in self.clients():
            if not client.closed: client.close()
        self.wait_threads()
    
    # Polled client handling
    def add_polled(self, client):
        self.log_debug(11, 'New polled client: %s', client.prefix)
        fd = client.fileno()
        self.polled[fd] = client
        if self.polling: self.polling.register(fd, self.flags)
    def remove_polled(self, fd):
        # Warning: Must be called in the same thread as the polling.
        # Outside of this class, call the client's close() method instead.
        self.log_debug(11, 'Removing polled client: %s',
                self.polled.pop(fd).prefix)
        if self.polling: self.polling.unregister(fd)
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
            client.close()
        elif event & select.POLLNVAL:
            # Assume that the socket has already been closed
            self.log_debug(7, 'Invalid fd for %s', client.prefix)
            self.remove_polled(fd)
    def clean_polled(self):
        # Warning: This doesn't catch closed players until their Clients close.
        for fd, client in self.polled.items():
            if client.closed: self.remove_polled(fd)
    
    # Timed client handling
    def add_timed(self, client, delay):
        self.log_debug(11, 'New timed client: %s', client.prefix)
        deadline = time() + delay
        self.timed.append((deadline, client))
        return deadline
    def add_dynamic(self, client):
        self.log_debug(11, 'New dynamic client: %s', client.prefix)
        self.dynamic.append(client)
    def get_timeout(self):
        now = time()
        times = [t for t in (client.time_left(now)
                for client in self.dynamic if not client.closed)
                if t is not None]
        when = [t for t,c in self.timed if not c.closed]
        if when: times.append(max(0, 0.005 + min(when) - now))
        if times: result = min(times)
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
    class ThreadClient(object):
        def __init__(self, target, *args, **kwargs):
            from itertools import chain
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
            thread = Thread(target=self.attempt, args=(client,))
            thread.start()
            self.threaded.append((thread, client))
        else:
            self.log_debug(11, 'Emulating threaded client: %s', client.prefix)
            self.attempt(client)
    def new_thread(self, target, *args, **kwargs):
        self.add_threaded(self.ThreadClient(target, *args, **kwargs))
    def add_client(self, player_class, **kwargs):
        from network import Client
        name = player_class.name or player_class.__name__
        client = Client(player_class, manager=self, **kwargs)
        result = client.open()
        if result:
            self.add_polled(client)
            self.log_debug(10, 'Opened a Client for ' + name)
        else: self.log_debug(7, 'Failed to open a Client for ' + name)
        return result and client
    def start_clients(self, game_id):
        for klass in self.autostart:
            self.add_client(klass, game_id=game_id)
    def wait_threads(self):
        for thread, client in self.threaded:
            while thread.isAlive():
                try: sleep(self.sleep_time)
                except KeyboardInterrupt:
                    if not client.closed: client.close()
                    print 'Still waiting for threads...'
    def clean_threaded(self):
        self.log_debug(14, 'Checking threaded clients')
        self.threaded = [item for item in self.threaded if item[0].isAlive()]

def run_player(player_class, allow_multiple=True, allow_country=True):
    name = player_class.name or player_class.__name__
    num = 1
    opts = {}
    countries = {}
    try:
        for arg in argv[1:]:
            try: num = int(arg)
            except ValueError:
                if len(arg) > 3 and arg[3] == '=':
                    if allow_country: countries[arg[:3].upper()] = int(arg[4:])
                    else: raise ValueError
                elif arg[:2] == '-v': Verbose_Object.verbosity = int(arg[2:])
                elif arg[0] == '-' or opts.has_key('host'): raise ValueError
                else:
                    index = arg.find(':')
                    if index >= 0:
                        opts['host'] = arg[:index]
                        opts['port'] = int(arg[index+1:])
                    else: opts['host'] = arg
            else:
                if not allow_multiple: raise ValueError
    except:
        if allow_multiple:
            print 'Usage: %s [host][:port] [number]%s [-v<level>]' % (argv[0],
                    allow_country and ' [power=passcode] ...' or '')
            print 'Connects <number> copies of %s to <host>:<port>' % name
        else:
            print 'Usage: %s [host][:port]%s -v<level>' % (argv[0],
                    allow_country and ' [power=passcode]' or '')
            print 'Connects a copy of %s to <host>:<port>' % name
    else:
        config.option_class.local_opts.update(opts)
        manager = ThreadManager()
        while num > 0 or countries:
            num -= 1
            if countries:
                nation, pcode = countries.popitem()
                result = manager.add_client(player_class,
                        power=nation, passcode=pcode)
            else: result = manager.add_client(player_class)
            if not result: print 'Failed to start %s.  Sorry.' % name
        manager.run()

def run_server(server_class, default_verbosity):
    from network   import ServerSocket
    verbosity = default_verbosity
    opts = {}
    try:
        for arg in argv[1:]:
            if arg[:2] == '-v': verbosity = int(arg[2:])
            elif arg[:2] == '-g':
                games = int(arg[2:])
                opts['games'] = games
                opts['number of games'] = games
            elif config.variants.has_key(arg):
                opts['variant'] = arg
                opts['default variant'] = arg
    except:
        print 'Usage: %s [-gGAMES] [-vLEVEL] [VARIANT]' % (argv[0],)
        print 'Serves GAMES games of VARIANT, with output verbosity LEVEL'
    else:
        config.option_class.local_opts.update(opts)
        Verbose_Object.verbosity = verbosity
        manager = ThreadManager()
        server = ServerSocket(server_class, manager)
        if server.open():
            manager.add_polled(server)
            manager.run()
        else: server.log_debug(1, 'Failed to open the server.')

# Todo: Use a full option-parsing system, instead of this ad-hoc stuff.
