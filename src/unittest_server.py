''' Unit tests for the Server module.
'''#'''

import unittest, config
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
        self.__super.__init__(client_id, None, client_id, server)
        self.player = player_class(self.handle_message, self.rep, **kwargs)
        for msg in self.queue: self.handle_message(msg)
    def write(self, message):
        self.player.handle_message(message)
        if self.player.closed: self.close()
    def close(self):
        if not self.closed: self.game.disconnect(self)
        self.closed = True
    def handle_message(self, message):
        if self.player:
            self.log_debug(4, '%3s >> %s', self.power_name(), message)
            self.server.handle_message(self, message)
        else: self.queue.append(message)
    def set_rep(self, representation): self.player.rep = representation

class ServerTestCase(unittest.TestCase):
    "Basic Server Functionality"
    class Fake_Player(Verbose_Object):
        ''' A false player, to test the network classes.
            Also useful to learn country passcodes.
        '''#'''
        name = 'Fake Player'
        def __init__(self, send_method, representation, **kwargs):
            from language import NME, IAM, SEL
            self.log_debug(9, 'Fake player started')
            self.closed = False
            self.power = power = kwargs.get('power')
            self.pcode = pcode = kwargs.get('passcode')
            self.queue = []
            self.send = send_method
            self.rep = representation
            if kwargs.has_key('game_id'): send_method(SEL(kwargs['game_id']))
            if power and pcode: send_method(IAM(power, pcode))
            else: send_method(NME(self.name, self.__class__.__name__))
        def close(self):
            self.log_debug(9, 'Closed')
            self.closed = True
        def handle_message(self, message):
            from language import OFF, HLO, MAP, SVE, LOD, YES, ADM
            self.log_debug(5, '<< %s', message)
            self.queue.append(message)
            if message[0] is HLO:
                self.power = message[2]
                self.pcode = message[5].value()
            elif message[0] in (MAP, SVE, LOD): self.send(YES(message))
            elif message[0] is OFF: self.close()
        def admin(self, line, *args):
            self.queue = []
            self.send(ADM(self.name, str(line) % args))
            return [msg.fold()[2][0] for msg in self.queue if msg[0] is ADM]
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
            'default variant' : 'standard',
            'close on disconnect' : True,
            'use internal server' : True,
            'host' : '',
            'timeout for select() without deadline' : 5,
            'publish order sets': False,
            'publish individual orders': False,
            'total years before setting draw': 3,
            'invalid message response': 'croak',
            'minimum player count for bots': 2,
    }
    def setUp(self):
        ''' Initializes class variables for test cases.'''
        self.set_verbosity(0)
        config.option_class.local_opts.update(self.game_options)
        self.manager = None
        self.server = None
    def tearDown(self):
        if self.server and not self.server.closed: self.server.close()
    def set_verbosity(self, verbosity): Verbose_Object.verbosity = verbosity
    def connect_server(self, clients, games=1):
        config.option_class.local_opts.update({'number of games' : games})
        self.manager = manager = Fake_Manager(clients)
        self.server = manager.server
    def connect_player(self, player_class, **kwargs):
        return self.manager.start_thread(player_class, **kwargs)
    def assertContains(self, item, series):
        self.failUnless(item in series,
                'Expected %r among %r' % (item, series))

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
    def assertAdminResponse(self, player, command, response):
        self.assertContains(response, player.admin('Server: %s', command))
    def assertUnauthorized(self, player, command):
        self.assertAdminResponse(player, command, self.unauth)

class Server_Admin_Bots(Server_Admin):
    "Starting bots with admin commands"
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
    def test_start_bot_replacement(self):
        "The master can start a bot to replace a disconnected power."
        game = self.server.default_game()
        self.connect_player(self.Fake_Player)
        self.connect_player(self.Fake_Player)
        self.connect_player(self.Fake_Player)
        out = self.connect_player(self.Fake_Player)
        out.close()
        self.master.admin('Ping.')
        self.assertAdminResponse(self.master, 'start holdbot as' + out.power,
                '1 bot started')
        self.failUnless(game.players[out.power.key].client)
    def test_start_bot_country(self):
        "The master can start a bot to take a specific country."
        from xtended import ITA
        game = self.server.default_game()
        old_client = game.players[ITA].client
        old_id = old_client and old_client.client_id
        self.assertAdminResponse(self.master, 'start holdbot as Italy',
                '1 bot started')
        new_client = game.players[ITA].client
        self.failUnless(new_client and new_client.client_id != old_id)
    def test_start_bot_illegal(self):
        "Bots cannot be started to take over players still in the game."
        from xtended import ITA
        game = self.server.default_game()
        self.connect_player(self.Fake_Player)
        self.connect_player(self.Fake_Player)
        self.connect_player(self.Fake_Player)
        self.connect_player(self.Fake_Player)
        old_client = game.players[ITA].client.client_id
        self.assertAdminResponse(self.master, 'start holdbot as Italy',
                'Italy is still in the game.')
        self.failUnlessEqual(game.players[ITA].client.client_id, old_client)
    def test_start_multiple_bots(self):
        "Exactly enough bots can be started to fill up the game."
        self.assertAdminResponse(self.master, 'start holdbots', '4 bots started')
    def test_start_bot_blocking(self):
        "Bots can only be started in games with enough players."
        self.backup.close()
        self.robot.close()
        self.master.admin('Ping.')
        self.assertAdminResponse(self.master, 'start holdbots',
                'Recruit more players first.')
    def test_start_bot_same_address(self):
        "Players are only counted if they're from different computers."
        for client in self.server.default_game().clients:
            client.address = 'localhost'
        self.assertAdminResponse(self.master, 'start holdbot',
                'Recruit more players first.')

class Server_Admin_Other(Server_Admin):
    "Other administrative messages handled by the server"
    
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
    def test_unknown_variant(self):
        self.assertAdminResponse(self.master, 'new unknown_variant game',
                'Unknown variant "unknown_variant"')
        self.failUnlessEqual(len(self.server.games), 1)
    def test_list_variants(self):
        items = self.master.admin('Server: list variants')
        self.assertContains('Known map variants: ', items[0])
        self.assertContains('standard', items[0])
    def test_help(self):
        self.assertAdminResponse(self.master, 'help',
                '  help - Lists admin commands recognized by the server')
    def test_help_caps(self):
        self.assertContains('  help - Lists admin commands recognized by the server',
                self.master.admin('HELP'))
    
    def test_duplicate_mastership(self):
        "Only one player should be a master at a time."
        self.assertAdminResponse(self.backup, 'become master',
                'This game already has a master.')
    def test_master_password(self):
        "A second player can become master with the right password"
        self.assertAdminResponse(self.backup,
                'become master %s' % self.server.options.password,
                'Master powers granted.')
    
    def test_eject_boot(self):
        "Players can be ejected using 'boot' as well as 'eject'."
        self.assertAdminResponse(self.master, 'boot Fake Player',
                'Fake Player (Fake_Player) has disconnected. Have 2 players and 0 observers. Need 5 to start.')
    def test_eject_multiple_unstarted(self):
        "Multiple players of the same name can be ejected before the game starts."
        self.connect_player(self.Fake_Player)
        self.assertAdminResponse(self.master, 'eject Fake Player',
                'Fake Player (Fake_Player) has disconnected. Have 2 players and 0 observers. Need 5 to start.')
    def test_eject_multiple_started(self):
        "Multiple players of the same name cannot be ejected after the game starts."
        self.connect_player(self.Fake_Player)
        self.connect_player(self.Fake_Player)
        self.connect_player(self.Fake_Player)
        self.connect_player(self.Fake_Player)
        self.assertAdminResponse(self.master, 'eject Fake Player',
                'Ambiguous player "fake player"')
    def test_eject_power_unstarted(self):
        "Powers cannot be ejected by power name before the game starts."
        game = self.server.default_game()
        name = game.judge.player_name(game.p_order[2])
        self.assertAdminResponse(self.master, 'eject ' + name,
                'Unknown player "%s"' % name.lower())
    def test_eject_power_started(self):
        "Powers can be ejected by power name after the game starts."
        self.connect_player(self.Fake_Player)
        self.connect_player(self.Fake_Player)
        self.connect_player(self.Fake_Player)
        self.connect_player(self.Fake_Player)
        name = self.server.default_game().judge.player_name(self.robot.power)
        self.assertAdminResponse(self.master, 'eject ' + name,
                'Passcode for %s: %d' % (name, self.robot.pcode))

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
    def test_start_game(self):
        self.master.admin('Server: start standard game')
        self.failUnlessEqual(len(self.server.games), 2)
    def test_second_connection(self):
        self.new_game()
        self.failUnlessEqual(len(self.server.games), 2)
        self.connect_player(self.Fake_Player)
        self.connect_player(self.Fake_Player)
        self.failUnlessEqual(len(self.server.games[1].clients), 2)
    def test_old_reconnect(self):
        self.new_game()
        self.failUnlessEqual(len(self.server.games), 2)
        self.server.default_game().close()
        self.connect_player(self.Fake_Player)
        self.failUnlessEqual(len(self.server.games[0].clients), 2)
    def test_old_bot_connect(self):
        game = self.server.default_game()
        self.connect_player(self.Fake_Player)
        self.new_game()
        self.master.admin('Server: become master')
        self.master.admin('Server: start holdbot')
        self.failUnlessEqual(len(game.clients), 3)
    def test_sailho_game(self):
        from language import MAP
        self.new_game('sailho')
        self.failUnlessEqual(len(self.server.games), 2)
        player = self.connect_player(self.Fake_Player)
        self.assertContains(MAP('sailho'), player.queue)
    def test_RM_change(self):
        self.new_game('sailho')
        newbie = self.connect_player(self.Fake_Player, game_id=0)
        self.assertContains('AUS', newbie.rep)
        self.failUnlessEqual(newbie.rep['AUS'], 0x4100)
    
    def test_SEL_reply(self):
        from language import LST, SEL
        self.master.queue = []
        self.master.send(SEL())
        params = self.server.default_game().options.get_params()
        self.assertContains(LST(0, 6, 'standard', params), self.master.queue)
    def test_LST_reply(self):
        from language import LST
        self.master.queue = []
        self.master.send(LST())
        params = self.server.default_game().options.get_params()
        self.assertContains(LST(0, 6, 'standard', params), self.master.queue)
    def test_multigame_LST_reply(self):
        from language import LST
        std_params = self.server.default_game().options.get_params()
        self.new_game('sailho')
        self.master.queue = []
        self.master.send(LST())
        sailho_params = self.server.default_game().options.get_params()
        self.assertContains(LST(0, 6, 'standard', std_params), self.master.queue)
        self.assertContains(LST(1, 4, 'sailho', sailho_params), self.master.queue)

class Server_Bugfix(ServerTestCase):
    "Test cases to reproduce bugs found."
    def test_robotic_key_error(self):
        # Introduced in revision 93; crashes the server.
        self.connect_server([])
        master = self.connect_player(self.Fake_Master)
        master.admin('Server: become master')
        master.admin('Server: start holdbot as'
                + self.server.default_game().p_order[0])
        master.admin('Server: start 5 holdbots')
        self.connect_player(self.Fake_Player)
    def test_hello_leak(self):
        from language import HLO
        self.connect_server([])
        player = self.connect_player(self.Fake_Player)
        player.send(HLO())
        for message in player.queue:
            if message[0] is HLO: self.fail('Server sent HLO before game start')
    def test_admin_forward(self):
        self.connect_server([])
        sender = self.connect_player(self.Fake_Player)
        recipient = self.connect_player(self.Fake_Player)
        sender.admin('Ping.')
        self.assertContains(ADM(sender.name, 'Ping.'), recipient.queue)
    
if __name__ == '__main__': unittest.main()

# vim: sts=4 sw=4 et tw=75 fo=crql1
