''' Unit tests for the Server module.
'''#'''

import unittest, config
from time      import sleep
from functions import Verbose_Object
from language  import ADM
from network   import Connection, Service
from server    import Server, Client_Manager

class Fake_Manager(Client_Manager):
    def __init__(self, player_classes):
        self.classes = player_classes
        self.players = []
        self.server = None
        self.server = Server(self.broadcast, self)
        self.start_clients()
    def async_start(self, player_class, number, callback=None, **kwargs):
        self.start_threads(player_class, number, callback, **kwargs)
    def close_threads(self):
        for player in self.players:
            if not player.closed: player.close()
    def start_thread(self, player_class, **kwargs):
        if not self.server: return None
        service = Fake_Service(len(self.players),
                self.server, player_class, **kwargs)
        self.players.append(service)
        return service.player
    def broadcast(self, message):
        self.log_debug(2, 'ALL << %s', message)
        for client in self.players: client.write(message)

class Fake_Service(Service):
    ''' Connects the Server straight to a player.
    '''#'''
    def __init__(self, client_id, server, player_class, **kwargs):
        self.queue = []
        self.player = None
        self.__super.__init__(client_id, None, server)
        self.player = player_class(self.handle_message, self.rep, **kwargs)
        self.send_list(self.queue)
    def write(self, message):
        if self.player:
            self.player.handle_message(message)
            if self.player.closed: self.close()
        else: self.queue.append(message)
    def close(self):
        if not self.closed: self.game.disconnect(self)
        self.closed = True
    def handle_message(self, message):
        self.server.handle_message(self, message)

class ServerTestCase(unittest.TestCase):
    "Basic Server Functionality"
    class Fake_Player(Verbose_Object):
        ''' A false player, to test the network classes.
            Also useful to learn country passcodes.
        '''#'''
        name = 'Fake Player'
        def __init__(self, send_method, representation, **kwargs):
            from language import NME, IAM
            self.log_debug(9, 'Fake player started')
            self.closed = False
            self.power = power = kwargs.get('power')
            self.pcode = pcode = kwargs.get('passcode')
            self.queue = []
            self.send = send_method
            self.rep = representation
            if power and pcode: send_method(IAM(power, pcode))
            else: send_method(NME(self.name, self.__class__.__name__))
        def close(self):
            self.log_debug(9, 'Closed')
            self.closed = True
        def handle_message(self, message):
            from language import OFF, HLO, MAP, SVE, LOD, YES, ADM
            self.log_debug(5, '<< %s', message)
            if message[0] is HLO:
                self.power = message[2]
                self.pcode = message[5].value()
            elif message[0] in (MAP, SVE, LOD): self.send(YES(message))
            elif message[0] is OFF: self.close()
            else: self.queue.append(message)
        def admin(self, line, *args):
            self.queue = []
            self.send(ADM(self.name, str(line) % args))
            return [msg.fold()[2][0] for msg in self.queue if msg[0] is ADM]
    class Disconnector(Fake_Player):
        sleep_time = 14
        name = 'Loose connection'
        def handle_message(self, message):
            from language import HLO, ADM
            self.__super.handle_message(message)
            if message[0] is HLO:
                sleep(self.sleep_time)
                self.send(ADM(str(self.power), 'Passcode: %d' % self.pcode))
                self.close()
    class Fake_Master(Fake_Player):
        name = 'Fake Human Player'
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
            'invalid message response': 'croak',
    }
    def setUp(self):
        ''' Initializes class variables for test cases.'''
        self.set_verbosity(0)
        config.option_class.local_opts.update(self.game_options)
        self.manager = None
        self.server = None
        self.threads = []
    def tearDown(self):
        if self.server and not self.server.closed: self.server.close()
        for thread in self.threads:
            while thread.isAlive(): thread.join(1)
    def set_verbosity(self, verbosity): Verbose_Object.verbosity = verbosity
    def connect_server(self, clients, games=1, **kwargs):
        config.option_class.local_opts.update({'number of games' : games})
        self.manager = manager = Fake_Manager(clients)
        self.server = manager.server
    def connect_server_threaded(self, clients, games=1, poll=True, **kwargs):
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
    def connect_player(self, player_class, **kwargs):
        return self.manager.start_thread(player_class, **kwargs)
    def connect_player_threaded(self, player_class):
        from network import Client
        client = Client(player_class)
        self.threads.append(client.start())
        return client.player

class Server_Basics(ServerTestCase):
    def test_timeout(self):
        "Thirty-second timeout for the Initial Message"
        self.set_verbosity(15)
        self.connect_server_threaded([])
        client = self.Fake_Client(False)
        client.open()
        sleep(45)
        client.read_error(client.opts.Timeout)
    def test_full_connection(self):
        "Seven fake players, polling if possible"
        self.set_verbosity(15)
        self.connect_server_threaded([self.Disconnector] * 7)
    def test_without_poll(self):
        "Seven fake players, selecting"
        self.set_verbosity(15)
        self.connect_server_threaded([self.Disconnector] * 7, poll=False)
    def test_with_timer(self):
        "Seven fake players and an observer"
        from player  import Clock
        self.connect_server([Clock] + ([self.Disconnector] * 7))
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
        class Fake_Restarter(self.Disconnector):
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
        self.connect_server_threaded([Fake_Restarter] + [self.Disconnector] * 6)

class Server_Admin(ServerTestCase):
    "Administrative messages handled by the server"
    unauth = 'You are not authorized to do that.'
    game_options = {}
    game_options.update(ServerTestCase.game_options)
    game_options['close on disconnect'] = False
    
    def setUp(self):
        ServerTestCase.setUp(self)
        self.connect_server([])
        self.master = self.connect_player(self.Fake_Master)
        self.become_master(self.master)
        self.backup = self.connect_player(self.Fake_Master)
        self.robot  = self.connect_player(self.Fake_Player)
    def become_master(self, player): player.admin('Server: become master')
    def assertContains(self, item, series):
        self.failUnless(item in series,
                'Expected %r among %r' % (item, series))
    def assertAdminResponse(self, player, command, response):
        self.assertContains(response, player.admin('Server: %s', command))
    def assertUnauthorized(self, player, command):
        self.assertAdminResponse(player, command, self.unauth)
    
    def test_start_bot(self):
        "Bot starting actually works"
        game = self.server.default_game()
        count = len(game.clients)
        self.master.admin('Server: start holdbot')
        self.failUnless(len(game.clients) > count)
        self.failIf(game.clients[-1].closed)
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
        self.become_master(self.backup)
        self.assertAdminResponse(self.backup, 'pause', 'Game paused.')
    def test_pause_robot(self):
        "Only a game master should pause the game"
        self.assertUnauthorized(self.robot, 'pause')
    
    def test_press_enable(self):
        "Whether the enable press option works"
        from language import FRM, PCE, PRP, SND, YES
        self.assertAdminResponse(self.master, 'enable press', 'Press level set to 8000.')
        sender = self.connect_player(self.Fake_Player)
        recipient = self.connect_player(self.Fake_Player)
        self.connect_player(self.Fake_Player)
        self.connect_player(self.Fake_Player)
        offer = PRP(PCE([sender.power, recipient.power]))
        msg = SND(0, recipient.power, offer)
        sender.send(msg)
        self.assertContains(YES(msg), sender.queue)
        msg = FRM([sender.power, 0], recipient.power, offer)
        self.assertContains(msg, recipient.queue)
    def test_press_disable(self):
        "Whether the disable press option works"
        from language import ERR, HUH, PCE, PRP, SND
        self.assertAdminResponse(self.master, 'disable press', 'Press level set to 0.')
        sender = self.connect_player(self.Fake_Player)
        recipient = self.connect_player(self.Fake_Player)
        self.connect_player(self.Fake_Player)
        self.connect_player(self.Fake_Player)
        offer = PRP(PCE([sender.power, recipient.power]))
        msg = SND(0, recipient.power, offer)
        sender.send(msg)
        self.assertContains(HUH([ERR, msg]), sender.queue)
    def test_press_master(self):
        "Whether a game master can enable press"
        self.assertAdminResponse(self.master, 'enable press', 'Press level set to 8000.')
    def test_press_backup(self):
        "Whether a backup game master can enable press"
        self.master.close()
        self.backup.admin('Ping')
        self.become_master(self.backup)
        self.assertAdminResponse(self.backup, 'enable press', 'Press level set to 8000.')
    def test_press_robot(self):
        "Only a game master should enable press"
        self.assertUnauthorized(self.robot, 'enable press')
    
    def test_cleanup(self):
        "Someone can connect to an abandoned game and end it."
        self.connect_player(self.Fake_Player)
        self.connect_player(self.Fake_Player)
        self.connect_player(self.Fake_Player)
        self.connect_player(self.Fake_Player)
        self.master.close()
        self.backup.close()
        self.robot.admin('Ping')
        game = self.server.default_game()
        new_master = self.connect_player(self.Fake_Master,
                power=self.master.power, passcode=self.master.pcode)
        self.become_master(new_master)
        new_master.admin('Server: end game')
        self.failUnless(game.closed)
    
    def test_duplicate_mastership(self):
        "Only one player should be a master at a time."
        self.assertAdminResponse(self.backup, 'become master',
                'This game already has a master.')
    def test_master_password(self):
        "A second player can become master with the right password"
        self.assertAdminResponse(self.backup,
                'become master %s' % self.server.options.password,
                'Master powers granted.')

class Server_Multigame(ServerTestCase):
    def setUp(self):
        ServerTestCase.setUp(self)
        self.connect_server([])
        self.master = self.connect_player(self.Fake_Master)
    def new_game(self, variant=None):
        self.master.admin('Server: new%s game' %
                (variant and ' '+variant or ''))
    def test_new_game(self):
        self.new_game()
        self.failUnlessEqual(len(self.server.games), 2)
        self.connect_player(self.Fake_Player)
        self.failUnless(len(self.server.games[1].clients))
    def test_second_connection(self):
        self.new_game()
        self.failUnlessEqual(len(self.server.games), 2)
        self.connect_player(self.Fake_Player)
        self.connect_player(self.Fake_Player)
        self.failUnlessEqual(len(self.server.games[1].clients), 2)
    def test_old_reconnect(self):
        self.new_game()
        self.failUnlessEqual(len(self.server.games), 2)
        for dummy in range(7): self.connect_player(self.Disconnector)
        self.connect_player(self.Fake_Player)
        self.failUnlessEqual(len(self.server.games[0].clients), 2)
    def test_old_bot_connect(self):
        self.new_game()
        self.master.admin('Server: start holdbot')
        self.failUnlessEqual(len(self.server.games[0].clients), 2)

class Server_FullGames(ServerTestCase):
    def connect_server(self, *args, **kwargs):
        super(Server_FullGames, self).connect_server(*args, **kwargs)
        while not self.server.closed: sleep(3); self.server.check()
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
