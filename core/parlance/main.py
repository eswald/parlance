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

from config    import Configuration, VerboseObject, variants
from fallbacks import any
from language  import protocol
from reactor   import ThreadManager


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
    
    def reconnect(self):
        r'''Whether to reconnect automatically.'''
        return False

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
    
    def __init__(self, manager):
        self.transport = None  # A protocol that accepts messages
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
        if self.transport:
            self.transport.close()
    def handle_input(self, line):
        try: message = self.rep.translate(line)
        except Exception, err: print str(err) or '??'
        else: self.send(message)
    def send(self, message):
        if self.transport and not self.closed:
            self.transport.write(message)
    
    def reconnect(self):
        r'''Whether to reconnect automatically.'''
        self.manager.close()
        return False

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
