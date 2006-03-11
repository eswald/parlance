''' Unit tests for the PyDip server module
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
'''#'''

import unittest, config
from time      import sleep, time
from functions import absolute_limit, Verbose_Object
from network   import Connection, Service
from server    import Server, Client_Manager, Judge

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
        It would probably be a bad idea to mix this with network Services.
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
    ''' Base class for Server unit tests'''
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
            from language import HLO, LOD, MAP, OFF, SVE, YES
            self.log_debug(5, '<< %s', message)
            self.queue.append(message)
            if message[0] is HLO:
                self.power = message[2]
                self.pcode = message[5].value()
            elif message[0] in (MAP, SVE, LOD): self.send(YES(message))
            elif message[0] is OFF: self.close()
        def admin(self, line, *args):
            from language import ADM
            self.queue = []
            self.send(ADM(self.name, str(line) % args))
            return [msg.fold()[2][0] for msg in self.queue if msg[0] is ADM]
        def get_time(self):
            from language import TME
            self.queue = []
            self.send(TME())
            times = [absolute_limit(msg[2].value())
                    for msg in self.queue if msg[0] is TME]
            return times and times[0] or None
    class Fake_Master(Fake_Player):
        name = 'Fake Human Player'
    class Fake_Client(Connection):
        ''' A fake Client to test the server timeout.'''
        is_server = False
        
        def __init__(self, send_IM):
            'Initializes instance variables'
            self.prefix = 'Fake Client'
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
            'syntax Level': 20,
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
            'time allowed for vetos': 3,
    }
    def setUp(self):
        ''' Initializes class variables for test cases.'''
        self.set_verbosity(20)
        config.option_class.local_opts.update(self.game_options)
        self.manager = None
        self.server = None
    def tearDown(self):
        if self.server and not self.server.closed: self.server.close()
    def set_verbosity(self, verbosity): Verbose_Object.verbosity = verbosity
    def connect_server(self, clients=(), games=1):
        config.option_class.local_opts.update({'number of games' : games})
        self.manager = manager = Fake_Manager(clients)
        self.server = manager.server
        self.game = self.server.default_game()
    def connect_player(self, player_class, **kwargs):
        return self.manager.start_thread(player_class, **kwargs)
    def start_game(self):
        game = self.server.default_game()
        while not game.started: self.connect_player(self.Fake_Player)
        return game
    def wait_for_actions(self, game=None):
        if not game: game = self.server.default_game()
        while game.actions:
            remain = game.max_time(time())
            if remain > 0: sleep(remain)
            game.check_flags()
    
    def assertPressSent(self, press, sender, recipient):
        from language import FRM, SND, YES
        sender.queue = []
        recipient.queue = []
        msg = SND(0, recipient.power, press)
        sender.send(msg)
        self.assertContains(YES(msg), sender.queue)
        msg = FRM([sender.power, 0], recipient.power, press)
        self.assertContains(msg, recipient.queue)
    def assertPressRejected(self, press, sender, recipient):
        from language import REJ, SND
        sender.queue = []
        msg = SND(0, recipient.power, press)
        sender.send(msg)
        self.assertContains(REJ(msg), sender.queue)
    def assertPressHuhd(self, press, sender, recipient, error_loc):
        from language import ERR, HUH, SND
        sender.queue = []
        msg = SND(0, recipient.power, press)
        sender.send(msg)
        msg.insert(error_loc, ERR)
        self.assertContains(HUH(msg), sender.queue)
    def assertContains(self, item, series):
        self.failUnless(item in series,
                'Expected %r among %r' % (item, series))

class Server_Admin(ServerTestCase):
    ''' Administrative messages handled by the server'''
    game_options = {}
    game_options.update(ServerTestCase.game_options)
    game_options['close on disconnect'] = False
    
    def setUp(self):
        ServerTestCase.setUp(self)
        self.connect_server()
        self.master = self.connect_player(self.Fake_Master)
        self.backup = self.connect_player(self.Fake_Master)
        self.robot  = self.connect_player(self.Fake_Player)
    def assertAdminResponse(self, player, command, response):
        from language import ADM
        if command:
            self.assertContains(response, player.admin('Server: %s', command))
        else:
            self.assertContains(response,
                [msg.fold()[2][0] for msg in player.queue if msg[0] is ADM])
    def failIfAdminContains(self, player, substring):
        from language import ADM
        messages = [msg.fold()[2][0] for msg in player.queue if msg[0] is ADM]
        for item in messages:
            if substring in item:
                self.fail('%r found within %s' % (substring, messages))
    def assertAdminVetoable(self, player, command, response):
        from functions import num2name
        self.assertEqual([response, '(You may veto within %s seconds.)' %
                    num2name(self.game_options['time allowed for vetos'])],
                player.admin('Server: %s', command))

class Server_Admin_Bots(Server_Admin):
    ''' Starting bots with admin commands'''
    def test_start_bot(self):
        ''' Players can start new bots in their current game.'''
        game = self.game
        count = len(game.clients)
        self.assertAdminVetoable(self.master, 'start holdbot',
                'Fake Human Player is starting a HoldBot.')
        self.wait_for_actions()
        self.failUnless(len(game.clients) > count)
        self.failIf(game.clients[-1].closed)
    def test_start_bot_veto(self):
        ''' Bot starting can be vetoed.'''
        game = self.game
        count = len(game.clients)
        self.master.admin('Server: start holdbot')
        self.assertAdminResponse(self.robot, 'veto start',
                'Fake Player has vetoed the HoldBot.')
        self.wait_for_actions()
        self.failIf(len(game.clients) > count)
    def test_start_bot_replacement(self):
        ''' The master can start a bot to replace a disconnected power.'''
        game = self.start_game()
        out = self.robot
        out.close()
        self.master.admin('Ping.')
        name = game.judge.player_name(out.power)
        self.assertAdminVetoable(self.master, 'start holdbot as' + out.power,
                'Fake Human Player is starting a HoldBot as %s.' % name)
        self.wait_for_actions()
        self.failUnless(game.players[out.power.key].client)
    def test_start_bot_country(self):
        ''' The master can start a bot to take a specific country.'''
        from xtended import ITA
        game = self.game
        old_client = game.players[ITA].client
        old_id = old_client and old_client.client_id
        self.assertAdminVetoable(self.master, 'start holdbot as italy',
                'Fake Human Player is starting a HoldBot as Italy.')
        self.wait_for_actions()
        new_client = game.players[ITA].client
        self.failUnless(new_client and new_client.client_id != old_id)
    def test_start_bot_illegal(self):
        ''' Bots cannot be started to take over players still in the game.'''
        from xtended import ITA
        game = self.start_game()
        old_client = game.players[ITA].client.client_id
        self.assertAdminResponse(self.master, 'start holdbot as Italy',
                'Italy is still in the game.')
        self.wait_for_actions()
        self.failUnlessEqual(game.players[ITA].client.client_id, old_client)
    def test_start_multiple_bots(self):
        ''' Exactly enough bots can be started to fill up the game.'''
        self.assertAdminVetoable(self.master, 'start holdbots',
                'Fake Human Player is starting four instances of HoldBot.')
        self.wait_for_actions()
        self.failUnless(self.game.started)
    def test_start_bot_blocking(self):
        ''' Bots can only be started in games with enough players.'''
        self.backup.close()
        self.robot.close()
        self.master.admin('Ping.')
        self.assertAdminResponse(self.master, 'start holdbots',
                'Recruit more players first, or use your own bots.')
    def test_start_bot_same_address(self):
        ''' Players are only counted if they're from different computers.'''
        for client in self.game.clients:
            client.address = 'localhost'
        self.assertAdminResponse(self.master, 'start holdbot',
                'Recruit more players first, or use your own bots.')

class Server_Admin_Local(Server_Admin):
    ''' Admin commands restricted to local connections'''
    def assertUnauthorized(self, player, command):
        self.assertAdminResponse(player, command,
                'You are not authorized to do that.')
    
    def setUp(self):
        Server_Admin.setUp(self)
        self.game.clients[1].address = '127.0.0.1'
    def test_shutdown_master(self):
        ''' Whether a non-local player can shut down the server'''
        self.assertUnauthorized(self.master, 'shutdown')
        self.failIf(self.server.closed)
    def test_shutdown_local(self):
        ''' Whether a local connection can shut down the server'''
        self.assertAdminResponse(self.backup, 'shutdown',
                'The server is shutting down.  Good-bye.')
        self.failUnless(self.server.closed)
    def test_status_request(self):
        ''' Whether a local connection can request game status information'''
        self.assertAdminResponse(self.backup, 'status',
                'Game 0: Have 3 players and 0 observers. Need 4 to start.')
    def test_power_listing(self):
        ''' Whether a local connection can power assignments'''
        game = self.game
        power = game.players[game.clients[1].country]
        self.assertAdminResponse(self.backup, 'powers',
                '%s (%d): Fake Human Player (Fake_Master), from 127.0.0.1'
                % (power.pname, power.passcode))

class Server_Admin_Press(Server_Admin):
    ''' Admin commands to change the press level of a game'''
    
    def test_press_enable(self):
        ''' The enable press admin command works'''
        from language import PCE, PRP, SCD, SUG
        from xtended  import LON, PAR
        self.assertAdminVetoable(self.master, 'enable press',
                'Fake Human Player is enabling press level 8000.')
        self.wait_for_actions()
        sender = self.backup
        recipient = self.robot
        self.start_game()
        
        # Level 10 succeeds
        offer = PRP(PCE([sender.power, recipient.power]))
        self.assertPressSent(offer, sender, recipient)
        # Level 40 succeeds
        offer2 = PRP(SCD([sender.power, LON], [recipient.power, PAR]))
        self.assertPressSent(offer2, sender, recipient)
        # Level 60 succeeds
        offer[0] = SUG
        self.assertPressSent(offer, sender, recipient)
    def test_press_enable_number(self):
        ''' The enable press admin command works with a numeric level'''
        from language import PCE, PRP, SCD, SUG
        from xtended  import LON, PAR
        self.assertAdminVetoable(self.master, 'enable press level 40',
                'Fake Human Player is enabling press level 40.')
        self.wait_for_actions()
        sender = self.backup
        recipient = self.robot
        self.start_game()
        
        # Level 10 succeeds
        offer = PRP(PCE([sender.power, recipient.power]))
        self.assertPressSent(offer, sender, recipient)
        # Level 40 succeeds
        offer2 = PRP(SCD([sender.power, LON], [recipient.power, PAR]))
        self.assertPressSent(offer2, sender, recipient)
        # Level 60 fails
        offer[0] = SUG
        self.assertPressHuhd(offer, sender, recipient, 8)
    def test_press_enable_verbal(self):
        ''' The enable press admin command works with a verbal level'''
        from language import PCE, PRP, SCD, SUG
        from xtended  import LON, PAR
        print config.press_levels
        self.assertAdminVetoable(self.master,
                'enable press level Sharing out the supply centres',
                'Fake Human Player is enabling press level 40.')
        self.wait_for_actions()
        sender = self.backup
        recipient = self.robot
        self.start_game()
        
        # Level 10 succeeds
        offer = PRP(PCE([sender.power, recipient.power]))
        self.assertPressSent(offer, sender, recipient)
        # Level 40 succeeds
        offer2 = PRP(SCD([sender.power, LON], [recipient.power, PAR]))
        self.assertPressSent(offer2, sender, recipient)
        # Level 60 fails
        offer[0] = SUG
        self.assertPressHuhd(offer, sender, recipient, 8)
    def test_press_disable(self):
        ''' The disable press admin command works'''
        from language import PCE, PRP
        self.assertAdminVetoable(self.master, 'disable press',
                'Fake Human Player is disabling press.')
        self.wait_for_actions()
        sender = self.backup
        recipient = self.robot
        self.start_game()
        
        # Level 10 fails
        offer = PRP(PCE([sender.power, recipient.power]))
        self.assertPressHuhd(offer, sender, recipient, 0)
    def test_press_window_block(self):
        ''' A vetoed enable press command blocks disabled press.'''
        from language import ERR, HUH, PRP, SCD, SND
        from xtended  import LON, PAR
        sender = self.backup
        recipient = self.robot
        self.start_game()
        self.master.admin('Server: enable press')
        offer = PRP(SCD([sender.power, LON], [recipient.power, PAR]))
        sender.queue = []
        msg = SND(0, recipient.power, offer)
        sender.send(msg)
        self.assertAdminResponse(self.robot, 'veto enable press',
                'Fake Player has vetoed the press level change.')
        self.wait_for_actions()
        msg.insert(10, ERR)
        self.assertContains(HUH(msg), sender.queue)
    def test_press_window_pass(self):
        ''' A vetoed disable press command passes enabled press.'''
        from language import FRM, SND, PCE, PRP, YES
        sender = self.backup
        recipient = self.robot
        self.start_game()
        self.master.admin('Server: disable press')
        sender.queue = []
        recipient.queue = []
        offer = PRP(PCE([sender.power, recipient.power]))
        msg = SND(0, recipient.power, offer)
        sender.send(msg)
        self.assertAdminResponse(self.robot, 'veto disable press',
                'Fake Player has vetoed the press level change.')
        self.wait_for_actions()
        self.assertContains(YES(msg), sender.queue)
        msg = FRM([sender.power, 0], recipient.power, offer)
        self.assertContains(msg, recipient.queue)
    def test_press_timeout_block(self):
        ''' A non-vetoed disable press command blocks press immediately.'''
        from language import ERR, HUH, FRM, SND, PCE, PRP
        sender = self.backup
        recipient = self.robot
        self.start_game()
        self.master.admin('Server: disable press')
        sender.queue = []
        offer = PRP(PCE([sender.power, recipient.power]))
        msg = SND(0, recipient.power, offer)
        sender.send(msg)
        self.wait_for_actions()
        self.assertContains(HUH([ERR, msg]), sender.queue)
    def test_press_timeout_pass(self):
        ''' A non-vetoed enable press command enables press immediately.'''
        from language import FRM, PRP, SCD, SND, YES
        from xtended  import LON, PAR
        sender = self.backup
        recipient = self.robot
        self.start_game()
        self.master.admin('Server: enable press')
        sender.queue = []
        recipient.queue = []
        offer = PRP(SCD([sender.power, LON], [recipient.power, PAR]))
        msg = SND(0, recipient.power, offer)
        sender.send(msg)
        self.wait_for_actions()
        self.assertContains(YES(msg), sender.queue)
        msg = FRM([sender.power, 0], recipient.power, offer)
        self.assertContains(msg, recipient.queue)

class Server_Admin_Eject(Server_Admin):
    def test_eject_player_unstarted(self):
        ''' Players can be ejected from the game.'''
        self.assertAdminVetoable(self.master, 'eject Fake Player',
                'Fake Human Player is ejecting Fake Player from the game.')
        self.wait_for_actions()
        self.assertAdminResponse(self.master, None,
                'Fake Player (Fake_Player) has disconnected. '
                'Have 2 players and 0 observers. Need 5 to start.')
    def test_eject_player_started(self):
        ''' A player can be ejected by name after the game starts.'''
        from player import HoldBot
        game = self.game
        while not game.started: self.connect_player(HoldBot)
        self.assertAdminVetoable(self.master, 'eject Fake Player',
                'Fake Human Player is ejecting Fake Player from the game.')
        self.wait_for_actions()
        name = game.judge.player_name(self.robot.power)
        self.assertAdminResponse(self.master, None,
                'Passcode for %s: %d' % (name, self.robot.pcode))
    def test_eject_multiple_unstarted(self):
        ''' Multiple players of the same name can be ejected before the game starts.'''
        self.connect_player(self.Fake_Player)
        self.assertAdminVetoable(self.master, 'eject Fake Player',
                'Fake Human Player is ejecting two instances of Fake Player from the game.')
        self.wait_for_actions()
        self.assertAdminResponse(self.master, None,
                'Fake Player (Fake_Player) has disconnected. '
                'Have 2 players and 0 observers. Need 5 to start.')
    def test_eject_multiple_started(self):
        ''' Multiple players of the same name cannot be ejected after the game starts.'''
        self.start_game()
        self.assertAdminResponse(self.master, 'eject Fake Player',
                'Ambiguous player "Fake player"')
    def test_eject_power_unstarted(self):
        ''' Powers cannot be ejected by power name before the game starts.'''
        game = self.game
        name = game.judge.player_name(game.p_order[2])
        self.assertAdminResponse(self.master, 'eject ' + name,
                'Unknown player "%s"' % name)
    def test_eject_power_started(self):
        ''' Powers can be ejected by power name after the game starts.'''
        game = self.start_game()
        name = game.judge.player_name(self.robot.power)
        self.assertAdminVetoable(self.master, 'eject ' + name,
                'Fake Human Player is ejecting %s from the game.' % name)
        self.wait_for_actions()
        self.assertAdminResponse(self.master, None,
                'Passcode for %s: %d' % (name, self.robot.pcode))
    
    def test_eject_player_veto(self):
        ''' Player ejection can be vetoed by a third party.'''
        self.master.admin('Server: eject Fake Player')
        self.assertAdminResponse(self.backup, 'veto eject',
                'Fake Human Player has vetoed the player ejection.')
        self.wait_for_actions()
        self.failIfAdminContains(self.master, 'disconnected')
    def test_eject_self_veto(self):
        ''' Player ejection can be vetoed by the ejected player.'''
        self.master.admin('Server: eject Fake Player')
        self.assertAdminResponse(self.robot, 'veto eject',
                'Fake Player has vetoed the player ejection.')
        self.wait_for_actions()
        self.failIfAdminContains(self.master, 'disconnected')
    def test_boot_player_unstarted(self):
        ''' Players can be ejected using 'boot' as well as 'eject'.'''
        self.assertAdminVetoable(self.master, 'boot Fake Player',
                'Fake Human Player is booting Fake Player from the game.')
    def test_boot_self_veto(self):
        ''' Player booting cannot be vetoed by the booted player.'''
        self.master.admin('Server: boot Fake Player')
        self.assertAdminResponse(self.robot, 'veto boot',
                "You can't veto your own booting.")
        self.wait_for_actions()
        self.assertAdminResponse(self.master, None,
                'Fake Player (Fake_Player) has disconnected. '
                'Have 2 players and 0 observers. Need 5 to start.')

class Server_Admin_Other(Server_Admin):
    ''' Other administrative messages handled by the server'''
    help_line = '  help - Lists admin commands recognized by the server'
    
    def test_pause(self):
        ''' Players can pause the game.'''
        self.start_game()
        self.assertAdminResponse(self.master, 'pause',
                'Fake Human Player has paused the game.')
        self.assertEqual(self.master.get_time(), None)
    def test_resume(self):
        ''' Players can resume a paused game.'''
        self.start_game()
        start = self.master.get_time()
        self.master.admin('Server: pause')
        sleep(7)
        self.assertAdminResponse(self.master, 'resume',
                'Fake Human Player has resumed the game.')
        end = self.master.get_time()
        self.failUnless(0 <= start - end <= 2,
                'Time difference: %g' % (start - end))
    
    def test_end_cleanup(self):
        ''' Someone can connect to an abandoned game and end it.'''
        game = self.start_game()
        self.master.close()
        self.backup.close()
        self.robot.admin('Ping')
        new_master = self.connect_player(self.Fake_Master,
                power=self.master.power, passcode=self.master.pcode)
        self.assertAdminVetoable(new_master, 'end game',
                'Fake Human Player is ending the game.')
        self.wait_for_actions()
        self.failUnless(game.closed)
    def test_end_veto(self):
        ''' An end game command can be vetoed.'''
        game = self.start_game()
        self.master.admin('Server: end game')
        self.assertAdminResponse(self.robot, 'veto end game',
                'Fake Player has vetoed ending the game.')
        self.wait_for_actions()
        self.failIf(game.closed)
    
    def test_unknown_variant(self):
        self.assertAdminResponse(self.master, 'new unknown_variant game',
                'Unknown variant "unknown_variant"')
        self.failUnlessEqual(len(self.server.games), 1)
    def test_list_variants(self):
        items = self.master.admin('Server: list variants')
        self.assertContains('Known map variants: ', items[0])
        self.assertContains('standard', items[0])
    def test_help(self):
        self.assertAdminResponse(self.master, 'help', self.help_line)
    def test_help_caps(self):
        self.assertContains(self.help_line, self.master.admin('HELP'))
    def test_help_server_caps(self):
        self.assertContains(self.help_line, self.master.admin('SERVER: HELP'))
    
    def test_who(self):
        ''' Player names can be listed, without reference to power.'''
        response = self.master.admin('Server: who')
        self.assertEqual(response, [
                'Fake Human Player (Fake_Master) x2',
                'Fake Player (Fake_Player)',
        ], response)

class Server_Multigame(ServerTestCase):
    def setUp(self):
        ServerTestCase.setUp(self)
        self.connect_server()
        self.master = self.connect_player(self.Fake_Master)
    def new_game(self, variant=None):
        self.master.admin('Server: new%s game' %
                (variant and ' '+variant or ''))
        return self.server.default_game()
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
        game = self.new_game()
        self.failUnlessEqual(len(self.server.games), 2)
        game.close()
        self.connect_player(self.Fake_Player)
        self.failUnlessEqual(len(self.server.games[0].clients), 2)
    def test_old_bot_connect(self):
        ''' Starting a bot connects it to your game, not the current one.'''
        game = self.server.default_game()
        self.connect_player(self.Fake_Player)
        self.new_game()
        self.master.admin('Server: start holdbot')
        self.wait_for_actions(game)
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
        params = self.game.options.get_params()
        self.assertContains(LST(0, 6, 'standard', params), self.master.queue)
    def test_LST_reply(self):
        from language import LST
        self.master.queue = []
        self.master.send(LST())
        params = self.game.options.get_params()
        self.assertContains(LST(0, 6, 'standard', params), self.master.queue)
    def test_multigame_LST_reply(self):
        from language import LST
        std_params = self.game.options.get_params()
        game = self.new_game('sailho')
        self.master.queue = []
        self.master.send(LST())
        sailho_params = game.options.get_params()
        self.assertContains(LST(0, 6, 'standard', std_params), self.master.queue)
        self.assertContains(LST(1, 4, 'sailho', sailho_params), self.master.queue)

class Server_Bugfix(ServerTestCase):
    ''' Test cases to reproduce bugs found.'''
    def test_robotic_key_error(self):
        # Introduced in revision 93; crashes the server.
        self.connect_server()
        master = self.connect_player(self.Fake_Master)
        master.admin('Server: start holdbot as' + self.game.p_order[0])
        master.admin('Server: start 5 holdbots')
        self.connect_player(self.Fake_Player)
    def test_hello_leak(self):
        from language import HLO
        self.connect_server()
        player = self.connect_player(self.Fake_Player)
        player.send(HLO())
        for message in player.queue:
            if message[0] is HLO: self.fail('Server sent HLO before game start')
    def test_admin_forward(self):
        from language import ADM
        self.connect_server()
        sender = self.connect_player(self.Fake_Player)
        recipient = self.connect_player(self.Fake_Player)
        sender.admin('Ping.')
        self.assertContains(ADM(sender.name, 'Ping.'), recipient.queue)
    def test_NPR_press_block(self):
        ''' The NPR parameter should block press during retreat phases.
            A code overview revealed that it probably doesn't.
        '''#'''
        from language import PCE, PRP
        from gameboard import Turn
        config.option_class.local_opts.update({
                'No Press during Retreats': True})
        self.connect_server()
        sender = self.connect_player(self.Fake_Player)
        recipient = self.connect_player(self.Fake_Player)
        game = self.start_game()
        game.judge.phase = Turn.retreat_phase
        game.set_deadlines()
        offer = PRP(PCE([sender.power, recipient.power]))
        self.assertPressRejected(offer, sender, recipient)
    def test_NPR_press_allow(self):
        ''' The NPR parameter should block press during retreat phases.
            A code overview revealed that it probably doesn't.
        '''#'''
        from language import PCE, PRP
        from gameboard import Turn
        config.option_class.local_opts.update({
                'No Press during Retreats': False})
        self.connect_server()
        sender = self.connect_player(self.Fake_Player)
        recipient = self.connect_player(self.Fake_Player)
        game = self.start_game()
        game.judge.phase = Turn.retreat_phase
        game.set_deadlines()
        offer = PRP(PCE([sender.power, recipient.power]))
        self.assertPressSent(offer, sender, recipient)
    
if __name__ == '__main__': unittest.main()
