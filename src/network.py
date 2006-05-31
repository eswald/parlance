''' PyDip client <-> server communications
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
    
    This should be the only module that cares about the client-server protocol.
'''#'''

import config, socket, select
from sys       import stdin
from copy      import copy
from time      import time, sleep
from struct    import pack, unpack
from language  import Message, Token, YES, REJ, ADM, OFF, MDF
from functions import Verbose_Object, any, s


class network_options(config.option_class):
    ''' Options used to establish DCSP connections.'''
    section = 'network'
    def __init__(self):
        self.echo_final   = self.getboolean('send unnecessary final messages', False)
        self.host         = self.getstring('host', '')
        self.port         = self.getint('port', 16713)
        self.wait_time    = self.getint('idle timeout for server loop', 600)
        
        error_number = self.getint('first error number', 1)
        default_errors = 'Timeout, NotIM, Endian, BadMagic, Version, DupIM, ServerIM, MessType, Short, QuickDM, NotRM, UnexpectedRM, ClientRM, IllegalToken'
        for code in self.getlist('error codes', default_errors):
            setattr(self, code, error_number)
            error_number += 1
    

class SocketWrapper(Verbose_Object):
    def __init__(self):
        self.opts = network_options()
        self.broken = False  # Whether the write pipe has been broken
        self.closed = False
        self.sock = None
    def close(self):
        if self.sock: self.sock.close()
        self.closed = True
        self.sock = None
    def open(self): raise NotImplementedError
    def run(self):  raise NotImplementedError
    def start(self):
        from threading import Thread
        try:
            if self.open():
                self.log_debug(10, 'Starting a thread')
                thread = Thread(target=self.run)
                thread.start()
                return thread
            else: self.log_debug(1, 'Failed to open')
        except socket.error, e: self.log_debug(1, 'Socket error %s', e.args)
        return None
    def check(self):
        ''' Called when we have data to read.'''
        raise NotImplementedError
    def fileno(self): return self.sock.fileno()

class Connection(SocketWrapper):
    ''' Base methods for the DAIDE Client-Server Protocol.'''
    is_server = NotImplemented
    
    def __init__(self):
        self.__super.__init__()
        self.send_final = True
        self.proto = config.protocol
        self.rep = None
        
        # IM, DM, FM, etc.
        for name, value in self.proto.message_types.iteritems():
            setattr(Connection, name[0] + 'M', value)
    def close(self):
        if self.send_final: self.send_dcsp(self.FM, '')
        self.send_final = False
        self.__super.close()
    
    # Incoming messages
    def read(self):
        if self.closed or not self.sock:
            self.log_debug(7, 'Reading while closed')
            return None
        try:
            header = self.sock.recv(4)
            if header and self.sock:
                msg_type, msg_len = unpack('!BxH', header)
                if msg_len: message = self.sock.recv(msg_len)
                else:       message = ''
                return self.process_message(msg_type, message)
            else:
                self.log_debug(7, 'Received empty packet')
                self.close()
        except socket.error, e:
            # Ignore 'Resource temporarily unavailable' errors
            # Anything else is probably a bad connection
            if e.args[0] == 11:
                self.log_debug(13, 'Ignoring socket error %s', e.args)
            else:
                self.log_debug(1, 'Socket error %s', e.args)
                # Should I disable the final message in this case?
                self.close()
        return None
    def process_message(self, type_code, data):
        ''' Processes a single DCSP message from the server.'''
        self.log_debug(13, 'Message type %d received', type_code)
        message = None
        if   type_code == self.IM:
            if self.is_server:     self.process_IM(data)
            else:                  self.send_error(self.opts.ServerIM)
        elif type_code == self.RM:
            if self.is_server:     self.send_error(self.opts.ClientRM)
            elif len(data) % 6:    self.send_error(self.opts.Short)
            #elif self.rep:         self.send_error(self.opts.UnexpectedRM)
            else:                  self.read_representation(data)
        elif type_code == self.DM:
            if not data:           self.send_error(self.opts.Short)
            elif len(data) % 2:    self.send_error(self.opts.Short)
            elif self.rep:         message = self.unpack_message(data)
            else:                  self.send_error(self.opts.QuickDM)
        elif type_code == self.FM: self.send_final = self.opts.echo_final; self.close()
        elif type_code == self.EM:
            if len(data) == 2:     self.send_error(unpack('!H', data)[0], True)
            else:                  self.send_error(self.opts.Short)
        else:
            self.log_debug(7, 'Unknown message type %s received', type_code)
            self.send_error(self.opts.MessType)
        return message
    def process_IM(self, data):
        ''' Verifies the Initial Message from the client.'''
        if len(data) == 4:
            (version, magic) = unpack('!HH', data)
            if magic == self.proto.magic:
                if version == self.proto.version:
                    self.deadline = None
                    self.send_RM()
                else: self.send_error(self.opts.Version)
            elif unpack('>H', pack('<H', magic)) == self.proto.magic:
                self.send_error(self.opts.Endian)
            else: self.send_error(self.opts.BadMagic)
        else: self.send_error(self.opts.Short)
    def read_representation(self, data):
        ''' Creates a representation dictionary from the RM.
            This dictionary maps names to numbers and vice-versa.
        '''#'''
        from translation import Representation
        if data:
            rep = {}
            while len(data) >= 6:
                num, name = unpack('!H3sx', data[:6])
                rep[num] = name
                data = data[6:]
            self.rep = Representation(rep, self.proto.base_rep)
        else: self.rep = self.proto.default_rep
    def unpack_message(self, data):
        ''' Produces a Message from a string of token numbers.
            Uses values in the representation, if available.
            
            >>> from translation import Representation
            >>> c = Connection()
            >>> c.rep = Representation({0x4101: 'Sth'}, c.proto.base_rep)
            >>> msg = [HLO.number, BRA.number, 0x4101, KET.number]
            >>> c.unpack_message(pack('!HHHH', *msg))
            Message([HLO, [Token('Sth', 0x4101)]])
        '''#'''
        try:
            result = Message([self.rep[x]
                for x in unpack('!' + 'H'*(len(data)//2), data)])
        except ValueError:
            # Someone foolishly chose to disconnect over an unknown token.
            self.send_error(self.opts.IllegalToken)
            result = None
        else:
            # Tokens in the "Reserved for AI use" category
            # must never be sent over the wire.
            if any('Reserved' in token.category_name() for token in result):
                self.send_error(self.opts.IllegalToken)
                result = None
        return result
    
    # Outgoing messages
    def write(self, message): self.send_dcsp(self.DM, message.pack())
    def send_error(self, code, from_them=False):
        if self.is_server: them = 'Client'; us = 'Server'
        else:              them = 'Server'; us = 'Client'
        
        text = self.proto.error_strings.get(code)
        if text:
            if from_them: faulty = us
            else: faulty = them; self.send_dcsp(self.EM, pack('!H', code))
            self.log_debug(8, '%s error (%s)', faulty, text)
        else:
            if from_them: sender = them + ' sent'
            else:         sender = us + ' trying to send'
            self.log_debug(7, '%s unknown error "%s"', sender, code)
        
        # Terminate the connection
        self.send_final = self.opts.echo_final
        self.close()
    def send_RM(self):
        ''' Sends the representation message to the client.
            This implementation always sends it,
            instead of relying on default behavior.
        '''#'''
        data = ''
        for name, token in self.rep.items():
            data += pack('!H3sx', token.number, name)
        self.send_dcsp(self.RM, data)
    def send_dcsp(self, msg_type, data):
        ''' Sends a DCSP message to the client.
            msg_type must be an integer, one of the defined message types.
            data must be a packed binary string.
        '''#'''
        if self.sock and not self.broken:
            self.log_debug(13, 'Sending message type %d', msg_type)
            try: self.sock.sendall(pack('!BxH', msg_type, len(data)) + data)
            except socket.error, e:
                # Don't close here, because there may be more to receive
                self.log_debug(7, 'Socket error while sending %s', e.args)
                self.send_final = False
                self.broken = True
        else: self.log_debug(7, 'Trying to send on a closed connection')

class Client(Connection):
    ''' Connects an internal Player to a server on the network.'''
    is_server = False
    def __init__(self, player_class, **kwargs):
        'Initializes instance variables'
        self.__super.__init__()
        self.pclass = player_class
        self.kwargs = kwargs
        self.player = None
    def prefix(self):
        return (self.player and self.player.prefix
                or self.pclass.__name__) + ' Client'
    prefix = property(fget=prefix)
    
    def check(self):
        msg = self.read()
        if msg:
            #self.log_debug(5, '<< %s', msg)
            try: self.player.handle_message(msg)
            except: self.close(); raise
        if self.player.closed: self.close()
    def send(self, msg):
        self.log_debug(5, '>> %s', msg)
        self.write(msg)
    
    def open(self):
        # Open the socket
        self.sock = sock = socket.socket()
        sock.connect((self.opts.host or 'localhost', self.opts.port))
        sock.settimeout(None)
        
        # Required by the DCSP document
        try: sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        except: self.log_debug(7, 'Could not set SO_KEEPALIVE')
        
        # Send initial message
        self.log_debug(9, 'Sending Initial Message')
        self.send_dcsp(self.IM, pack('!HH', self.proto.version, self.proto.magic));
        
        # Wait for representation message
        while not (self.closed or self.rep):
            result = self.read()
            if result: self.log_debug(7, str(result) + ' while waiting for RM')
        if self.rep: self.log_debug(9, 'Representation received')
        
        # Set a reasonable timeout.
        # Without this, we don't check for client death until
        # the next server message; in some cases, until it dies.
        # With it, the client may die prematurely.
        #sock.settimeout(30)
        
        # Create the Player
        if self.rep and not self.closed:
            self.player = self.pclass(self.send, self.rep, **self.kwargs)
            self.player.register()
            return True
        else: return False
    def close(self):
        if self.player and not self.player.closed: self.player.close()
        self.__super.close()
    def run(self):
        ''' The main client loop.'''
        try:
            while not self.player.closed:
                msg = self.read()
                if msg: self.player.handle_message(msg)
        except KeyboardInterrupt: self.log_debug(1, 'Killed by user')
        except: self.close(); raise
        self.close()

class Service(Connection):
    ''' Connects a network player to the internal Server.'''
    is_server = True
    def __init__(self, client_id, connection, address, server):
        self.__super.__init__()
        self.sock      = connection
        self.client_id = client_id
        self.deadline  = time() + 30
        self.address   = address
        self.country   = None
        self.name      = None
        self.version   = None
        self.guesses   = 0
        self.mastery   = False
        self.booted    = False
        self.server    = server
        self.errors    = 0
        self.game      = server.default_game()
        self.rep       = self.game.variant.rep
        self.prefix    = self.game.prefix + ', #' + str(client_id)
    def power_name(self):
        return self.country and str(self.country) or ('#' + str(self.client_id))
    def full_name(self):
        return (self.name and ('%s (%s)' % (self.name, self.version))
                or 'An observer')
    def check(self):
        msg = self.read()
        if msg:
            self.log_debug(4, '%3s >> %s', self.power_name(), msg)
            try: self.server.handle_message(self, msg)
            except Exception, e:
                self.log_debug(1, '%s handling "%s": %s',
                        e.__class__.__name__, msg, e)
                self.server.broadcast_admin('An error has occurred.  '
                        'The server may be unreliable until it is restarted.')
                self.errors += 1
                if self.errors > 3:
                    self.admin("You have caused too much trouble.  Good-bye.")
                    self.boot()
                else: self.admin("Please don't do that again, whatever it was.")
    def close(self):
        if not self.closed:
            self.game.disconnect(self)
            self.__super.close()
    def boot(self):
        ''' Forcibly disconnect a client, for misbehaving or being replaced.'''
        self.log_debug(6, 'Booting client #%d', self.client_id)
        self.send(+OFF)
        self.booted = self.country
        self.country = None
        self.close()
    def set_rep(self, representation):
        if representation != self.rep:
            self.rep = representation
            self.send_RM()
    
    def send(self, message):
        if message[0] is MDF: text = 'MDF [...]'
        else: text = str(message)
        self.log_debug(3, '%3s << %s', self.power_name(), text)
        self.write(message)
    def send_list(self, message_list):
        for msg in message_list: self.send(msg)
    def accept(self, message): self.send(YES(message))
    def reject(self, message): self.send(REJ(message))
    def admin(self, line, *args): self.send(ADM('Server')(str(line) % args))

class ServerSocket(SocketWrapper):
    try: flags = select.POLLIN | select.POLLERR | select.POLLHUP | select.POLLNVAL
    except AttributeError: flags = None
    
    def __init__(self, server_class, *server_args):
        self.__super.__init__()
        self.server = None
        self.server_class = server_class
        self.server_args = server_args
        self.deadline = None
        self.log_debug(10, 'Attempting to create a poll object')
        if self.flags:
            try: self.polling = select.poll()
            except: self.polling = None
        else: self.polling = None
        self.sockets = {}
        self.next_id = 0
    def open(self):
        ''' Start listening for clients on the specified address.
            May throw exceptions for bad host/port combinations.
        '''#'''
        # Initialize a new socket
        wait_time = .125
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        addr = (self.opts.host, self.opts.port)
        while True:
            try: sock.bind(addr)
            except socket.error, e:
                if e.args[0] == 98:
                    self.log_debug(6, 'Waiting for port %s:%d' % addr)
                    sleep(wait_time)
                    wait_time *= 2
                else: raise e
            else: break
        sock.setblocking(False)
        sock.listen(7)
        self.sock = sock
        self.add(self)
        # FIXME: Temporary hack to enable RawServer
        self.server_class.fd_handler = self.add
        self.server = self.server_class(self.broadcast, *self.server_args)
        return bool(sock and self.server)
    def close(self):
        if self.server and not self.server.closed: self.server.close()
        self.closed = True
        for client in self.sockets.values():
            if not client.closed: client.close()
        #if self.sock: self.remove(self.fileno())
        self.__super.close()
    def check(self):
        ''' Attempts to connect one new network player'''
        try: conn, addr = self.sock.accept()
        except socket.error: pass
        else:
            self.log_debug(6, 'Connection from %s as client #%d',
                    addr, self.next_id)
            
            # Required by the DCSP document
            try: conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            except: self.log_debug(7, 'Could not set SO_KEEPALIVE')
            conn.setblocking(False)
            self.add(Service(self.next_id, conn, addr[0], self.server))
            self.next_id += 1
    def add(self, sock):
        fd = sock.fileno()
        self.sockets[fd] = sock
        if self.polling: self.polling.register(fd, self.flags)
    def remove(self, fd):
        # Warning: Only to be used from run() or one of its calls
        del self.sockets[fd]
        if self.polling: self.polling.unregister(fd)
        remain = len(self.sockets) - 1
        self.log_debug(6, '%d client%s still connected.', remain, s(remain))
        if not remain: self.server.check_close()
    def select(self, time_left):
        for fd, sock in self.sockets.items():
            if sock.closed: self.remove(fd)
        try: ready = select.select(self.sockets.values(), [], [], time_left)[0]
        except select.error, e:
            self.log_debug(7, 'Select error received: %s', e.args)
            if e.args[0] == 9:
                # Bad file descriptor
                #self.sockets = [sock for sock in self.sockets if not sock.closed]
                pass
            else: self.close(); raise
        else:
            if ready:
                for sock in ready:
                    self.log_debug(13, 'Checking %s', sock.prefix)
                    sock.check()
            else: return False
        return True
    def poll(self, time_left):
        try: ready = self.polling.poll(time_left * 1000)
        except select.error, e:
            self.log_debug(7, 'Polling error received: %s', e.args)
            # Ignore interrupted system calls
            if e.args[0] != 4:
                self.close()
                raise
        else:
            if ready:
                for fd, event in ready:
                    sock = self.sockets[fd]
                    self.log_debug(15, 'Event %s received for %s', event, sock.prefix)
                    if event & select.POLLIN:
                        self.log_debug(13, 'Checking %s', sock.prefix)
                        sock.check()
                    if sock.closed:
                        self.log_debug(7, '%s closed itself', sock.prefix)
                        self.remove(fd)
                    elif sock.broken:
                        self.log_debug(7, 'Done receiving from %s', sock.prefix)
                        self.remove(fd)
                        sock.close()
                    elif event & (select.POLLERR | select.POLLHUP):
                        self.log_debug(7, 'Event %s received for %s', event, sock.prefix)
                        self.remove(fd)
                        sock.close()
                    elif event & select.POLLNVAL:
                        # Assume that the socket has already been closed
                        self.log_debug(7, 'Invalid fd for %s', sock.prefix)
                        self.remove(fd)
            else: return False
        return True
    def run(self):
        ''' The main server loop; never returns until the server closes.'''
        self.log_debug(10, 'Internal server loop started')
        try:
            while not self.server.closed:
                timeout = self.get_deadline()
                method = self.polling and self.poll or self.select
                self.log_debug(14, '%s()ing for %.3f seconds', method.__name__, timeout)
                if not method(timeout):
                    self.log_debug(13, 'Checking clients and the server')
                    now = time()
                    for fd, client in self.sockets.items():
                        if None != client.deadline < now:
                            client.send_error(self.opts.Timeout)
                            self.remove(fd)
                    self.server.check()
            self.log_debug(11, 'Server loop ended')
        except KeyboardInterrupt:
            self.server.broadcast_admin('The server has been killed.  Good-bye.')
        except:
            self.log_debug(1, 'Error in server loop; closing')
            self.close()
            raise
        self.close()
        self.log_debug(11, 'End of run()')
    def get_deadline(self):
        now = time()
        result = self.server.deadline()
        if result is None:
            time_left = [(client.deadline - now)
                    for client in self.sockets.values() if client.deadline]
            if time_left: result = max([0, 0.005 + min(time_left)])
            else: result = self.opts.wait_time
        return result
    def broadcast(self, message):
        self.log_debug(2, 'ALL << %s', message)
        for client in self.sockets.values(): client.write(message)
    
    # For compatibility with other types of sockets
    def power_name(self): return '#' + str(self.next_id)
    def write(self, message): pass

class InputWaiter(Verbose_Object):
    ''' File descriptor for waiting on standard input.'''
    def __init__(self, supervisor):
        self.supervisor = supervisor
        self.deadline = None
        self.broken = False
        self.closed = False
    def fileno(self): return stdin.fileno()
    def check(self):
        line = ''
        try: line = raw_input()
        except EOFError: self.close()
        if line: self.supervisor.handle_input(line)
    def close(self):
        self.closed = True
        if not self.supervisor.closed: self.supervisor.close()
    def write(self, message): pass

class RawServer(Verbose_Object):
    ''' Simple server to translate DM to and from text.'''
    def __init__(self, broadcast_method):
        from server import server_options
        class FakeGame(Verbose_Object):
            def __init__(self, variant_name):
                self.variant = config.variants.get(variant_name)
            def disconnect(self, client):
                print 'Client #%d has disconnected.' % client.client_id
        
        self.closed = False
        self.broadcast = broadcast_method
        self.options = server_options()
        self.game = FakeGame(self.options.variant)
        self.rep = self.game.variant.rep
        self.input = InputWaiter(self)
        self.fd_handler(self.input)
        print 'Waiting for connections...'
    def handle_message(self, client, message):
        ''' Process a new message from the client.'''
        print '#%d >> %s' % (client.client_id, message)
    def close(self):
        ''' Informs the user that the connection has closed.'''
        self.closed = True
        if not self.input.closed: self.input.close()
    def check(self):
        ''' Nothing to do.'''
        pass
    def check_close(self):
        ''' All clients have disconnected.'''
        self.close()
    def handle_input(self, line):
        try: message = self.rep.translate(line)
        except Exception, err: print str(err) or '??'
        else: self.broadcast(message)
    def deadline(self): return None
    def broadcast_admin(self, text): pass
    def default_game(self): return self.game

if __name__ == '__main__':
    from main import run_server
    run_server(RawServer)
