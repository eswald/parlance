''' Unit tests for the Server module.
'''#'''

import unittest, config
from time      import sleep
from functions import Verbose_Object
from language  import ADM

class ServerTestCase(unittest.TestCase):
    "Basic Server Functionality"
    from network import Connection
    class Fake_Player(Verbose_Object):
        ''' A false player, to test the network classes.
            Also useful to learn country passcodes.
        '''#'''
        sleep_time = 14
        name = 'Loose connection'
        def __init__(self, send_method, representation, game_id=None):
            from language import NME
            self.log_debug(9, 'Fake player started')
            self.closed = False
            self.queue = []
            self.send = send_method
            self.rep = representation
            send_method(NME(self.name, self.__class__.__name__))
        def close(self):
            self.log_debug(9, 'Closed')
            self.closed = True
        def handle_message(self, message):
            from language import HLO, MAP, SVE, LOD, YES, ADM
            self.log_debug(5, '<< %s', message)
            if message[0] is HLO:
                self.power = message[2]
                self.pcode = message[5].value()
                sleep(self.sleep_time)
                self.send(ADM(str(self.power), 'Passcode: %d' % self.pcode))
                self.close()
            elif message[0] in (MAP, SVE, LOD): self.send(YES(message))
            else: self.queue.append(message)
        def admin(self, line, *args):
            self.queue = []
            self.send(ADM(self.name, str(line) % args))
            sleep(5)
            return [msg.fold()[2][0] for msg in self.queue if msg[0] is ADM]
    class Fake_Client(Connection):
        ''' A fake Client to test the server timeout.'''
        is_server = False
        def prefix(self): return 'Fake Client'
        prefix = property(fget=prefix)
        
        def __init__(self, send_IM):
            'Initializes instance variables'
            self.__super.__init__()
            self.initialize = send_IM
        def open(self):
            import socket
            # Open the socket
            self.sock = sock = socket.socket()
            sock.connect((self.opts.host, self.opts.port))
            sock.settimeout(None)
            
            # Required by the DCSP document
            try: sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            except: self.log_debug(7, 'Could not set SO_KEEPALIVE')
            
            if self.initialize:
                # Send initial message
                self.log_debug(9, 'Sending Initial Message')
                self.send_dcsp(self.IM, pack('!HH', self.opts.dcsp_version, self.opts.magic));
                
                # Wait for representation message
                while not (self.closed or self.rep):
                    result = self.read()
                    if result: self.log_debug(7, str(result) + ' while waiting for RM')
                if self.rep: self.log_debug(9, 'Representation received')
                
                # Set a reasonable timeout.
                # Without this, we don't check for client death until
                # the next server message; in some cases, until it dies.
                #sock.settimeout(30)
                
                # Create the Player
                if self.rep and not self.closed:
                    self.player = self.pclass(self.send, self.rep, **self.kwargs)
                    return True
            return False
        def read_error(self, code):
            self.log_debug(1, 'Expecting error #%d (%s)',
                    code, config.error_strings.get(code))
            self.error_code = None
            self.read()
            assert self.error_code == code
        def send_error(self, code, from_them=False):
            if from_them: self.error_code = code
            self.__super.send_error(code, from_them)
    
    game_options = {
            'syntax Level': 0,
            'variant name' : 'standard',
            'close on disconnect' : True,
            'use internal server' : True,
            'host' : '',
            'port' : 16719,
            'timeout for select() without deadline' : 5,
            'publish order sets': False,
            'publish individual orders': False,
            'total years before setting draw': 3,
    }
    def setUp(self):
        ''' Initializes class variables for test cases.'''
        self.set_verbosity(7)
        config.option_class.local_opts.update(self.game_options)
        self.server = None
        self.threads = []
    def tearDown(self):
        if self.server and not self.server.closed: self.server.close()
        for thread in self.threads:
            while thread.isAlive(): thread.join(1)
    def set_verbosity(self, verbosity): Verbose_Object.verbosity = verbosity
    def connect_server(self, clients, games=1, poll=True, **kwargs):
        from network import ServerSocket, Client
        config.option_class.local_opts.update({'number of games' : games})
        socket = ServerSocket()
        if not poll: socket.polling = None
        s_thread = socket.start()
        self.server = server = socket.server
        assert s_thread and server
        self.threads.append(s_thread)
        try:
            for dummy in range(games):
                assert not server.closed
                threads = []
                for player_class in clients:
                    thread = Client(player_class, **kwargs).start()
                    assert thread
                    threads.append(thread)
                for thread in threads:
                    if thread.isAlive(): thread.join()
        except:
            self.threads.extend(threads)
            server.close()
            raise
    def connect_player(self, player_class):
        from network import Client
        client = Client(self.Fake_Player)
        self.threads.append(client.start())
        return client.player

class Server_Basics(ServerTestCase):
    def test_timeout(self):
        "Thirty-second timeout for the Initial Message"
        self.set_verbosity(15)
        self.connect_server([])
        client = self.Fake_Client(False)
        client.open()
        sleep(45)
        client.read_error(client.opts.Timeout)
    def test_full_connection(self):
        "Seven fake players, polling if possible"
        self.set_verbosity(15)
        self.connect_server([self.Fake_Player] * 7)
    def test_without_poll(self):
        "Seven fake players, selecting"
        self.set_verbosity(15)
        self.connect_server([self.Fake_Player] * 7, poll=False)
    def test_with_timer(self):
        "Seven fake players and an observer"
        from player  import Clock
        self.connect_server([Clock] + ([self.Fake_Player] * 7))
    def test_takeover(self):
        "Takeover ability after game start"
        class Fake_Takeover(Verbose_Object):
            ''' A false player, who takes over a position and then quits.'''
            sleep_time = 7
            def __init__(self, send_method, representation, power, passcode):
                from language import IAM
                self.log_debug(9, 'Fake player started')
                self.restarted = False
                self.closed = False
                self.send = send_method
                self.rep = representation
                self.power = power
                send_method(IAM(power, passcode))
            def close(self):
                self.log_debug(9, 'Closed')
                self.closed = True
            def handle_message(self, message):
                from language import YES, IAM, ADM
                self.log_debug(5, '<< %s', message)
                if message[0] is YES and message[2] is IAM:
                    self.send(ADM(self.power.text, 'Takeover successful'))
                    sleep(self.sleep_time)
                    self.close()
                else: raise AssertionError, 'Unexpected message: ' + str(message)
        class Fake_Restarter(self.Fake_Player):
            ''' A false player, who starts Fake_Takeover after receiving HLO.'''
            sleep_time = 3
            def close(self):
                from network import Client
                thread = Client(Fake_Takeover, power=self.power,
                    passcode=self.pcode).start()
                assert thread
                thread.join()
                self.log_debug(9, 'Closed')
                self.closed = True
        self.set_verbosity(15)
        self.connect_server([Fake_Restarter] + [self.Fake_Player] * 6)

class Server_Admin(ServerTestCase):
    "Administrative messages handled by the server"
    unauth = 'You are not authorized to do that.'
    game_options = {}
    game_options.update(ServerTestCase.game_options)
    game_options['close on disconnect'] = False
    
    class Fake_Master(ServerTestCase.Fake_Player):
        name = 'Fake Human Player'
    def setUp(self):
        ServerTestCase.setUp(self)
        self.connect_server([])
        self.master = self.connect_player(self.Fake_Master)
        self.backup = self.connect_player(self.Fake_Master)
        self.robot  = self.connect_player(self.Fake_Player)
        while True:
            while self.robot.queue:
                msg = self.robot.queue.pop()
                if msg[0] is ADM and 'Have 3 players' in msg.fold()[2][0]:
                    return
            sleep(5)
    def assertContains(self, item, series):
        self.failUnless(item in series,
                'Expected %r among %r' % (item, series))
    def assertAdminResponse(self, player, command, response):
        self.assertContains(response, player.admin('Server: %s', command))
    def assertUnauthorized(self, player, command):
        self.assertAdminResponse(player, command, self.unauth)
    
    def test_start_bot(self):
        "Bot starting actually works"
        count = len(self.server.threads)
        self.master.admin('Server: start holdbot')
        self.failUnless(len(self.server.threads) > count)
        self.failIf(self.server.threads[-1][1].closed)
    def test_start_bot_master(self):
        "Whether a game master can start new bots"
        self.assertAdminResponse(self.master, 'start holdbot', '1 bot started')
    def test_start_bot_client(self):
        "Only a game master should start new bots"
        self.assertUnauthorized(self.robot, 'start holdbot')
    def test_pause_master(self):
        "Whether a game master can pause the game"
        self.assertAdminResponse(self.master, 'pause', 'Game paused.')
    def test_pause_backup(self):
        "Whether a backup game master can pause the game"
        self.master.close()
        self.backup.admin('Ping')
        sleep(5)
        self.assertAdminResponse(self.backup, 'pause', 'Game paused.')
    def test_pause_robot(self):
        "Only a game master should pause the game"
        self.assertUnauthorized(self.robot, 'pause')

class Server_Multigame(ServerTestCase):
    def setUp(self):
        ServerTestCase.setUp(self)
        self.connect_server([])
        self.master = self.connect_player(self.Fake_Player)
    def new_game(self, variant=None):
        self.master.admin('Server: new%s game' %
                (variant and ' '+variant or ''))
        sleep(5)
    def test_new_game(self):
        self.new_game()
        self.failUnlessEqual(len(self.server.games), 2)
        game_tester = self.connect_player(self.Fake_Player)
        sleep(5)
        self.failUnless(len(self.server.games[1].clients))

class Server_FullGames(ServerTestCase):
    def test_holdbots(self):
        "Seven drawing holdbots"
        from player import HoldBot
        self.connect_server([HoldBot] * 7)
    def test_one_dumbbot(self):
        "Six drawing holdbots and a dumbbot"
        from player  import HoldBot
        from dumbbot import DumbBot
        self.set_verbosity(1)
        DumbBot.verbosity = 20
        self.connect_server([DumbBot, HoldBot, HoldBot,
                HoldBot, HoldBot, HoldBot, HoldBot])
    def test_dumbbots(self):
        "seven dumbbots, quick game"
        from dumbbot import DumbBot
        self.connect_server([DumbBot] * 7)
    def test_two_games(self):
        "seven holdbots; two games"
        self.set_verbosity(4)
        from player import HoldBot
        self.connect_server([HoldBot] * 7, 2)

if __name__ == '__main__': unittest.main()

# vim: sts=4 sw=4 et tw=75 fo=crql1
