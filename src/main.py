''' PyDip user interface (such as it is)
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
'''#'''

import select
from itertools import chain
from sys import argv
from threading import Thread
from time import sleep, time

import config
from functions import Verbose_Object

__all__ = [
    'ThreadManager',
    'run_player',
    'run_server',
]

class ThreadManager(Verbose_Object):
    ''' Manages three types of clients: polled, timed, and threaded.
        Each type of client must have a close() method and corresponding
        closed property.  A client will be removed if it closes itself, and
        will be closed by the loop when the ThreadManager closes.
        
        Each client must also have a prefix property, which should be a string,
        and a run() method, which is called as described below.
        
        Polled clients have a fileno(), which indicates a file descriptor.
        The client's run() method is called whenever that file descriptor
        has input to process.  In addition, the client is closed when its
        file descriptor runs out of input.  Each file descriptor can only
        support one polled client.
        
        The run() method of a timed client is called after the amount of
        time specified when it is registered.  The specified delay is a
        minimum, not an absolute; polled clients take precedence.
        
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
        self.closed = False
        
        # Todo: Make these configurable
        self.wait_time = 600
        self.sleep_time = 1
    def clients(self):
        return [item[1] for item in chain(self.polled.iteritems(),
                self.timed, self.threaded)]
    
    def run(self):
        ''' The main loop; never returns until the manager closes.'''
        self.log_debug(10, 'Main loop started')
        try:
            while not self.closed:
                timeout = self.get_timeout()
                result = False
                if self.polled:
                    method = self.polling and self.poll or self.select
                    self.log_debug(14, '%s()ing for %.3f seconds',
                            method.__name__, timeout)
                    result = method(timeout)
                elif self.timed: sleep(timeout)
                elif self.threaded: sleep(self.sleep_time)
                else: self.close()
                if not result:
                    if self.timed: self.check_timed()
                    elif self.threaded: self.clean_threaded()
            self.log_debug(11, 'Main loop ended')
        except KeyboardInterrupt:
            self.log_debug(7, 'Interrupted by user')
        except:
            self.log_debug(1, 'Error in main loop; closing')
            self.close()
            raise
        self.close()
    def attempt(self, client):
        self.log_debug(12, 'Running %s', client.prefix)
        try: client.run()
        except Exception, e:
            self.log_debug(1, 'Exception running %s: %s %s',
                    client.prefix, e.__class__.__name__, e.args)
            if not client.closed: client.close()
            # Todo: Allow configuration to re-raise the error,
            # or at least print the traceback.
    
    # Polled client handling
    def add_polled(self, client):
        fd = client.fileno()
        self.polled[fd] = client
        if self.polling: self.polling.register(fd, self.flags)
    def remove_polled(self, fd):
        # Warning: Only to be used from run() or one of its calls;
        # elsewhere, call the close() method of the client.
        del self.polled[fd]
        if self.polling: self.polling.unregister(fd)
    def select(self, timeout):
        for fd, client in self.polled.items():
            if client.closed: self.remove_polled(fd)
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
    
    # Timed client handling
    def add_timed(self, client, delay):
        deadline = time() + delay + 0.005
        self.timed.append((deadline, client))
    def get_timeout(self):
        now = time()
        deadlines = [deadline for deadline, client in self.timed]
        if deadlines: result = max(0, min(deadlines) - now)
        else: result = self.wait_time
        return result
    def check_timed(self):
        self.log_debug(14, 'Checking timed clients')
        now = time()
        timed = self.timed
        self.timed = []
        for deadline, client in timed:
            if client.closed: continue
            if deadline < now: self.attempt(client)
            else: self.timed.append((deadline, client))
    
    # Threaded client handling
    def add_threaded(self, client):
        thread = Thread(target=self.attempt, args=(client))
        thread.start()
        self.threaded.append((thread, client))
    def close(self):
        self.closed = True
        self.clean_threaded()
        for client in self.clients():
            if not client.closed: client.close()
        for thread, client in self.threaded:
            while thread.isAlive():
                try: sleep(self.sleep_time)
                except KeyboardInterrupt:
                    print 'Still waiting for threads...'
    def clean_threaded(self):
        self.log_debug(14, 'Checking threaded clients')
        self.threaded = [item for item in self.threaded if item[0].isAlive()]

def run_player(player_class, allow_multiple=True, allow_country=True):
    from network   import Client
    class ClientThread(object):
        def __init__(self, client):
            self.client = client
            self.fileno = client.fileno
            self.close = client.close
            self.run = client.check
            self.prefix = client.prefix
        @property
        def closed(self): return self.client.closed
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
                client = Client(player_class, power=nation, passcode=pcode)
            else: client = Client(player_class)
            if client.open():
                manager.add_polled(ClientThread(client))
            else: print 'Failed to start %s.  Sorry.' % name
        manager.run()

def run_server(server_class, *server_args):
    from network   import ServerSocket
    verbosity = 7
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
        server = ServerSocket(server_class, *server_args)
        if server.open(): server.run()
        else: server.log_debug(1, 'Failed to open the server.')

# Todo: Use a full option-parsing system, instead of this ad-hoc stuff.
