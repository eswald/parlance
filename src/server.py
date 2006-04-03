''' PyDip game server
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
    
    Do not run this module directly; instead, run the package module.
    That avoids having a duplicate server module imported elsewhere.
'''#'''

import config, re
from random    import randint, shuffle
from time      import time
from gameboard import Map, Turn
from functions import any, s, expand_list, DefaultDict, Verbose_Object
from functions import absolute_limit, relative_limit, num2name, instances
from language  import *

import player, evilbot, dumbbot, peacebot, blabberbot, project20m
bots = dict([(klass.name.lower(), klass) for klass in
    player.HoldBot,
    dumbbot.DumbBot,
    evilbot.EvilBot,
    peacebot.PeaceBot,
    blabberbot.BlabberBot,
    project20m.Project20M,
])

class main_options(config.option_class):
    ''' Options used to start clients and the server, including:
        - verbosity    How much debug or logging information to display
        - external     A list of external programs to start each game
        - clients      A list of internal clients to start each game
        - countries    A mapping of country -> passcode to start as
        - fill         The internal client used to fill empty slots each game
    '''#'''
    section = 'main'
    def __init__(self):
        self.clients     = self.getlist('clients', '')
        self.countries   = {}
        self.external    = []
        self.fill        = None
        self.verbosity   = self.getint('output verbosity', 1)
class server_options(config.option_class):
    ''' Options for the server, including:
        - takeovers    Whether to allow taking over an existing power
        - snd_admin    Whether to send admin messages created by the server
        - fwd_admin    Whether to send admin messages from other players
        - games        Number of games to play
    '''#'''
    section = 'server'
    def __init__(self):
        self.takeovers = self.getboolean('allow takeovers',        False)
        self.replaced  = self.getboolean('show replaced powers in summary', False)
        self.snd_admin = self.getboolean('send admin messages',    False)
        self.admin_cmd = self.getboolean('accept admin commands',  False)
        self.fwd_admin = self.getboolean('forward admin messages', False)
        self.quit      = self.getboolean('close on disconnect',    False)
        self.shuffle   = self.getboolean('randomize power assignments', True)
        self.variant   = self.getstring( 'default variant',        'standard')
        self.games     = self.getint(    'number of games',        1)
        self.veto_time = self.getint(    'time allowed for vetos', 20)
        self.bot_min   = self.getint(    'minimum player count for bots', 0)

class Command(object):
    def __init__(self, pattern, callback, help):
        self.pattern = re.compile(pattern)
        self.command = callback
        self.description = help
class DelayedAction(object):
    def __init__(self, action, veto_action, veto_line, terms, delay, *args):
        self.callback = action
        self.veto_callback = veto_action
        self.veto_line = veto_line
        self.terms = terms
        self.args = args
        self.when = time() + delay
    def veto(self, client):
        ''' Cancels the action, calling the veto action if it was given.
            The veto callback may return a true value to block the cancellation,
            which should be a string explaining why it was blocked.
        '''#'''
        block = self.veto_callback and self.veto_callback(client, *self.args)
        if block:
            client.admin(block)
        else:
            if self.veto_line:
                client.game.admin('%s has vetoed %s',
                        client.full_name(), self.veto_line)
            client.game.actions.remove(self)
    def call(self):
        if self.callback: self.callback(*self.args)

class Client_Manager(Verbose_Object):
    def __init__(self):
        opts = main_options()
        self.classes = [klass for klass in opts.clients if klass]
        self.reserved = len(opts.clients) - len(self.classes)
        self.threads = []
    def start_clients(self):
        for klass in self.classes: self.start_thread(klass)
    def async_start(self, player_class, number, callback=None, **kwargs):
        from threading import Thread
        thread = Thread(target=self.start_threads,
                args=(player_class, number, callback), kwargs=kwargs)
        self.threads.append((thread, None))
        thread.start()
    def start_threads(self, player_class, number, callback=None, **kwargs):
        success = failure = 0
        for dummy in range(number):
            if self.start_thread(player_class, **kwargs):
                success += 1
            else: failure += 1
        if callback: callback(success, failure)
        return success, failure
    def start_thread(self, player_class, **kwargs):
        from network import Client
        client = Client(player_class, **kwargs)
        thread = client.start()
        if thread:
            self.threads.append((thread, client))
            self.log_debug(10, 'Client %s opened' % player_class.__name__)
        else: self.log_debug(7, 'Client %s failed to open' % player_class.__name__)
        return thread
    def close_threads(self):
        for thread, client in self.threads:
            if client and not client.closed: client.close()
            while thread.isAlive(): thread.join(1)

class Server(Verbose_Object):
    ''' Coordinates messages between clients and the games,
        administering socket connections and game creation.
    '''#'''
    
    def __init__(self, broadcast_function, client_manager):
        ''' Initializes instance variables, including:
            - options          Option defaults for this program
        '''#'''
        self.__super.__init__()
        self.options   = server_options()
        self.broadcast = broadcast_function
        self.manager   = client_manager
        self.games     = []
        self.closed    = False
        if not self.start_game():
            self.log_debug(1, 'Unable to start default variant')
            self.close()
    
    def deadline(self):
        now = time()
        time_left = [t for t in [game.max_time(now) for game in self.games]
            if t is not None]
        if time_left: return max([0, min(time_left)])
        else: return None
    def check(self):
        open_games = [game for game in self.games if not game.closed]
        if open_games:
            for game in open_games: game.check_flags()
        elif 0 < self.options.games <= len(self.games):
            if not any([g.clients for g in self.games]):
                self.log_debug(11, 'Completed all requested games')
                self.close()
        else: self.start_game()
    
    def broadcast_admin(self, text):
        if self.options.snd_admin: self.broadcast(ADM('Server', text))
    
    def handle_message(self, client, message):
        'Processes a single message from any client.'
        reply = message.validate(client.game.options.LVL)
        if reply: client.send(reply)
        else:
            method_name = 'handle_'+message[0].text
            # Special handling for common prefixes
            if message[0] in (YES, REJ, NOT):
                method_name += '_' + message[2].text
            
            handlers = [self, client.game, client.game.judge]
            for item in handlers:
                method = getattr(item, method_name, None)
                if method: method(client, message); break
            else:
                self.log_debug(7, 'Missing message handler: %s', method_name)
                client.send(HUH([ERR, message]))
    def handle_HUH(self, client, message):
        self.log_debug(7, 'Client #%d complained about message: %s',
                client.client_id, message)
    def handle_ADM(self, client, message):
        line = message.fold()[2][0]
        text = line.lower()
        if text[0:7] == 'server:': self.seek_command(client, text[7:])
        elif not re.search('[a-z]', line): self.seek_command(client, text)
        elif self.options.fwd_admin:
            if text[0:4] == 'all:': self.broadcast(message)
            else: client.game.broadcast(message)
        else: client.reject(message)
    def seek_command(self, client, text):
        if not self.options.admin_cmd:
            client.admin('Admin commands have been disabled.')
            return
        for pattern in self.commands:
            match = pattern.pattern.search(text)
            if match:
                pattern.command(self, client, match)
                break
        else:
            for pattern in client.game.commands:
                match = pattern.pattern.search(text)
                if match:
                    pattern.command(client.game, client, match)
                    break
            else:
                for pattern in self.local_commands:
                    match = pattern.pattern.search(text)
                    if match:
                        if client.address in ('localhost', '127.0.0.1'):
                            pattern.command(self, client, match)
                        else: client.admin('You are not authorized to do that.')
                        break
                else: client.admin('Unrecognized command: "%s"', text.strip())
    def handle_SEL(self, client, message):
        if len(message) > 3:
            reply = self.join_game(client, message[2].value()) and YES or REJ
            client.send(reply(message))
        else: client.game.send_listing(client)
    def handle_PNG(self, client, message): client.accept(message)
    def handle_LST(self, client, message):
        for game in self.games: game.send_listing(client)
    
    def default_game(self):
        games = list(self.games)
        games.reverse()
        for game in games:
            if not game.closed: return game
        else: return self.start_game()
    def join_game(self, client, game_id):
        if client.game.game_id == game_id: return True
        elif game_id < len(self.games):
            client.game.disconnect(client)
            new_game = self.games[game_id]
            client.game = new_game
            client.set_rep(new_game.variant.rep)
            return True
        else: return False
    def start_game(self, client=None, match=None):
        if match and match.lastindex:
            var_name = match.group(2)
        else: var_name = self.options.variant
        variant = config.variants.get(var_name)
        if variant:
            game_id = len(self.games)
            if client: client.admin('New game started, with id %s.', game_id)
            game = Game(self, game_id, variant)
            self.games.append(game)
            self.manager.start_clients()
            return game
        elif client: client.admin('Unknown variant "%s"', var_name)
        return None
    def select_game(self, client, match):
        try: num = int(match.group(1))
        except ValueError:
            client.admin('The game_id must be an integer.')
        else:
            if self.join_game(client, num):
                client.admin('Joined game #%d.', num)
            else: client.admin('Unknown game #%d.', num)
    
    def list_variants(self, client, match):
        names = config.variants.keys()
        names.sort()
        client.admin('Known map variants: %s', expand_list(names))
    def list_help(self, client, match):
        for line in ([
            #'Begin an admin message with "All:" to send it to all players, not just the ones in the current game.',
            'Begin an admin message with "Server:" to use the following commands, all of which are case-insensitive:',
        ] + [pattern.description for pattern in self.commands]
        + [pattern.description for pattern in client.game.commands]):
            client.admin(line)
    def list_bots(self, client, match):
        client.admin('Available types of bots:')
        for bot_class in bots.itervalues():
            client.admin('  %s - %s', bot_class.name, bot_class.description)
    def list_status(self, client, match):
        for game in self.games:
            message = None
            if not game.closed:
                if game.started:
                    if game.paused: message = 'Paused'
                    else: message = 'In progress'
                else: message = 'Forming'
            elif game.clients: message = 'Closed'
            if message:
                client.admin('Game %s: %s; %s', game.game_id,
                        message, game.has_need())
    def list_powers(self, client, match):
        for player in client.game.players.values():
            if player.client:
                client.admin('%s (%d): %s, from %s', player.pname,
                        player.passcode, player.full_name(),
                        player.client.address)
            else: client.admin('%s (%d): None', player.pname, player.passcode)
    def close(self, client=None, match=None):
        ''' Tells clients to exit, and closes the server's sockets.'''
        if not self.closed:
            self.broadcast_admin('The server is shutting down.  Good-bye.')
            self.log_debug(10, 'Closing')
            self.closed = True
            for game in self.games:
                if not game.closed: game.close()
            self.broadcast(OFF())
            self.manager.close_threads()
            self.log_debug(11, 'Done closing')
        else: self.log_debug(11, 'Duplicate close() call')
    
    commands = [
        Command(r'help', list_help,
            '  help - Lists admin commands recognized by the server'),
        Command(r'new game', start_game,
            '  new game - Starts a new game of Standard Diplomacy'),
        Command(r'(new|start) (\w+) game', start_game,
            '  new <variant> game - Starts a new game, with the <variant> map'),
        #Command(r'select game #?(\w+)', select_game,
        #    '  select game <id> - Switches to game <id>, if it exists'),
        Command(r'list variants', list_variants,
            '  list variants - Lists known map variants'),
        Command(r'list bots', list_bots,
            '  list bots - Lists bots that can be started by the server'),
    ]
    local_commands = [
        Command(r'shutdown', close,
            '  shutdown - Stops the server'),
        Command(r'status', list_status,
            '  status - Displays the status of each game'),
        Command(r'powers', list_powers,
            '  powers - Displays the power assignments for this game'),
    ]


class Game(Verbose_Object):
    ''' Coordinates messages between Players and the Judge,
        administering time limits and power assignments.
        
        Note: This implementation accepts press and other messages after
        the deadlines, until network traffic stops.  That prevents mass
        amounts of last-second traffic from preventing someone's orders
        from going through, but can be abused.
    '''#'''
    class Player_Struct(object):
        def __init__(self, power_name):
            self.client   = None
            self.name     = ''
            self.version  = ''
            self.ready    = False
            self.pname    = power_name
            self.robotic  = False
            self.assigned = False
            self.passcode = randint(100, Token.opts.max_pos_int - 1)
        def new_client(self, client, assigned=False):
            self.client   = client
            self.ready    = False
            if assigned:
                name, version = self.assigned
                self.robotic  = True
                self.assigned = False
            else:
                name = client.name or self.name
                version = client.version or self.version
                self.robotic  = 'Human' not in name + version
            self.name    = client.name = name
            self.version = client.version = version
        def client_ready(self): return self.client and self.ready
        def copy_client(self, struct):
            self.name    = struct.name
            self.ready   = struct.ready
            self.client  = struct.client
            self.version = struct.version
            self.robotic = struct.robotic
        def full_name(self): return '%s (%s)' % (self.name, self.version)
    
    def __init__(self, server, game_id, variant):
        ''' Initializes the plethora of instance variables:
            
            # Configuration and status information
            - server           The overarching server for the program
            - game_id          The unique identification for this game
            - options          The game_options instance for this game
            - judge            The judge, handling orders and adjudication
            - press_allowed    Whether press is allowed right now
            - started          Whether the game has started yet
            - closed           Whether the server is trying to shut down
            
            # Timing and press information
            - timers           Time notification requests
            - deadline         When the current turn will end
            - press_deadline   When press must stop for the current turn
            - time_checked     When time notifications were last sent
            - time_left        Time remaining when the clock stopped
            - press_in         Whether press is allowed during a given phase
            - limits           The time limits for the phases, as well as max and press
            
            # Player information
            - clients          List of Clients that have accepted the map
            - players          Power token -> player mappings
            - p_order          The order in which to assign powers
        '''#'''
        
        self.server         = server
        self.game_id        = game_id
        self.variant        = variant
        self.prefix         = 'Game %d' % game_id
        
        self.judge          = variant.new_judge()
        self.options        = game = self.judge.game_opts
        self.press_allowed  = False
        self.started        = False
        self.closed         = False
        self.paused         = False
        
        self.timers         = {}
        self.deadline       = None
        self.press_deadline = None
        self.time_checked   = None
        self.time_left      = None
        self.actions        = []
        
        move_limit = absolute_limit(game.MTL)
        press_limit = absolute_limit(game.PTL)
        build_limit = absolute_limit(game.BTL)
        retreat_limit = absolute_limit(game.RTL)
        self.press_in = {
            Turn.move_phase    : press_limit < move_limit or not move_limit,
            Turn.retreat_phase : not game.NPR,
            Turn.build_phase   : not game.NPB,
        }
        
        self.limits = {
            None               : 0,
            Turn.move_phase    : move_limit,
            Turn.retreat_phase : retreat_limit,
            Turn.build_phase   : build_limit,
            'press'            : press_limit,
        }
        
        self.clients        = []
        self.players        = {}
        self.limbo          = {}
        self.summary        = []
        powers = self.judge.players()
        if server.options.shuffle: shuffle(powers)
        else: powers.sort()
        self.p_order        = powers
        for country in powers:
            self.players[country] = self.Player_Struct(self.judge.player_name(country))
    
    # Connecting and disconnecting players
    def open_position(self, country):
        ''' Frees the player slot to be taken over,
            and either broadcasts the CCD message (during a game),
            or tries to give it to the oldest client in limbo.
        '''#'''
        player = self.players[country]
        player.client = None
        player.ready = True
        if self.closed: pass
        elif self.judge.phase:
            self.broadcast(CCD(country))
            pcode = 'Passcode for %s: %d' % (player.pname, player.passcode)
            self.log_debug(6, pcode)
            if not self.judge.eliminated(country):
                #self.admin(pcode)
                if self.options.DSD: self.pause()
        elif self.limbo: self.offer_power(country, *self.limbo.popitem())
    def offer_power(self, country, client, message):
        ''' Sets the client as the player for the power,
            pending acceptance of the map.
        '''#'''
        self.log_debug(6, 'Offering %s to client #%d', country, client.client_id)
        msg = message.fold()
        client.country = country
        client.name = msg[1][0]
        client.version = msg[2][0]
        self.players[country].new_client(client)
        client.send_list([YES(message), MAP(self.judge.map_name)])
    def players_unready(self):
        ''' A list of disconnected or unready players.'''
        return [country
            for country, struct in self.players.iteritems()
            if not (struct.client_ready() or self.judge.eliminated(country))
        ]
    def disconnect(self, client):
        self.log_debug(6, 'Client #%d has disconnected', client.client_id)
        self.cancel_time_requests(client)
        opening = None
        if client in self.clients:
            self.clients.remove(client)
            need = self.closed and ' ' or self.has_need()
            name = client.full_name()
            if client.booted:
                player = self.players[client.booted]
                if player.client is client:
                    reason = 'booted'
                    opening = client.booted
                else: reason = 'replaced'
                self.admin('%s has been %s. %s', name, reason, need)
            elif client.country:
                player = self.players[client.country]
                if self.closed or not self.started:
                    self.admin('%s has disconnected. %s', name, need)
                opening = client.country
                client.country = None
            else: self.admin('%s has disconnected. %s', name, need)
        elif client.country:
            # Rejected the map
            opening = client.country
            client.country = None
        elif self.limbo.has_key(client): del self.limbo[client]
        
        # For testing purposes: stop the game if a player quits
        if opening and not self.closed:
            quitting = self.server.options.quit
            self.log_debug(11, 'Deciding whether to quit (%s)', quitting)
            if quitting: self.close()
            else: self.open_position(opening)
        
        # Perhaps close the server
        if self.closed and not self.clients: self.server.check()
    def close(self):
        self.log_debug(10, 'Closing')
        self.pause()
        self.judge.phase = None
        if not self.closed:
            self.closed = True
            if self.started: self.broadcast(self.summarize())
        
        # Perhaps close the server
        if not self.clients: self.server.check()
    def reveal_passcodes(self, client):
        disconnected = {}
        robotic = {}
        for country, player in self.players.iteritems():
            if not self.judge.eliminated(country):
                if not player.client: disconnected[country] = player.passcode
                elif player.robotic: robotic[country] = player.passcode
        msg = None
        slate = None
        if disconnected:
            if len(disconnected) > 1: msg = 'have been disconnected'
            else: msg = 'has been disconnected'
            slate = disconnected
        elif robotic and self.server.options.takeovers:
            if len(robotic) > 1: msg = 'seem to be bots'
            else: msg = 'seems to be a bot'
            slate = robotic
        if msg:
            client.admin('%s %s.',
                expand_list(['%s (%s)' % kv for kv in slate.iteritems()]), msg)
            return True
        return False
    def players_needed(self):
        ''' Calculates the number of empty powers in the game.'''
        return len([p for p in self.players.itervalues() if not p.client])
    def has_need(self):
        ''' Creates the line announcing connected and needed players.'''
        observing = len([True for client in self.clients if not client.country])
        have      = len(self.clients) - observing
        needed    = len(self.players) - have
        need = ''
        if not self.started:
            if needed: need = 'Need %d to start.' % needed
            else: need = 'Game on!'
        elif needed and not self.closed:
            need = '%d player%s disconnected.' % (needed, s(needed))
        return 'Have %d player%s and %d observer%s. %s' % (
                have, s(have), observing, s(observing), need)
    def check_start(self):
        needed = len(self.players_unready())
        if needed:
            self.log_debug(9, 'Waiting for %d more player%s', needed, s(needed))
        else:
            # Send starting messages, and start the timers.
            self.started = True
            self.log_debug(9, 'Starting the game')
            for user in self.clients: self.send_hello(user)
            for user, message in self.limbo.iteritems():
                user.reject(message)
                self.reveal_passcodes(user)
            self.limbo.clear()
            self.broadcast_list(self.judge.start())
            self.set_deadlines()
    
    # Time Limits
    def pause(self):
        if self.deadline:
            self.time_left = self.deadline - time()
            self.deadline = self.press_deadline = None
            self.broadcast(NOT(TME(relative_limit(self.time_left))))
        self.paused = True
    def set_deadlines(self, seconds=None):
        ''' Sets the press_allowed flag and starts turn timers.
            Use seconds when the clock starts again after DSD.
        '''#'''
        phase = self.judge.phase
        if not seconds:
            seconds = self.limits[phase]
            self.press_allowed = (phase and self.press_in[phase])
            self.time_checked = seconds
        self.deadline = self.press_deadline = self.time_left = None
        if seconds and not self.closed:
            message = TME(relative_limit(seconds))
            if self.paused:
                self.time_left = seconds
                self.broadcast(NOT(message))
            else:
                self.deadline = time() + seconds
                if self.press_allowed and phase == Turn.move_phase:
                    self.press_deadline = self.deadline - self.limits['press']
                self.broadcast(message)
    def max_time(self, now):
        ''' Returns the number of seconds before the next event.
            May return None if there is no next event scheduled.
        '''#'''
        if self.ready(): return 0
        result = None
        if self.deadline:
            timers = [sec for sec in self.timers if sec < self.time_checked]
            timers.append(self.press_deadline and self.limits['press'] or 0)
            result = self.deadline - max(timers)
        if self.actions:
            next_action = min([a.when for a in self.actions])
            if result: result = min(next_action, result)
            else: result = next_action
        return result and result - now
    def cancel_time_requests(self, client):
        ''' Removes the client from the list of time requests.'''
        for client_list in self.timers.itervalues():
            while client in client_list: client_list.remove(client)
    def check_flags(self):
        ''' Checks deadlines, time requests, wait flags, and delayed actions,
            running the judge and sending notifications when appropriate.
        '''#'''
        now = time()
        for act in list(self.actions):
            if act.when <= now: act.call(); self.actions.remove(act)
        if self.ready(): self.run_judge()
        elif self.deadline:
            remain = self.deadline - now
            for second in [sec for sec in self.timers if remain < sec < self.time_checked]:
                self.time_checked = second
                for client in self.timers[second]:
                    client.send(TME(relative_limit(second)))
            if now > self.deadline: self.run_judge()
            elif self.press_deadline and now > self.press_deadline:
                self.press_allowed  = False
                self.press_deadline = None
    def ready(self): return not (self.paused or self.judge.unready or self.players_unready())
    def run_judge(self):
        ''' Runs the judge and handles turn transitions.'''
        if self.deadline: self.log_debug(10, 'Running the judge with %f seconds left', self.deadline - time())
        else: self.log_debug(10, 'Running the judge')
        self.broadcast_list(self.judge.run())
        if self.judge.phase:
            self.set_deadlines()
            for player in self.players.itervalues():
                if player.client: player.ready = True
        else: self.close()
    def queue_action(self, client, action_callback, action_line,
            veto_callback, veto_line, veto_terms, *args):
        delay = self.server.options.veto_time
        self.admin('%s is %s', client.full_name(), action_line)
        if delay > 0:
            self.actions.append(DelayedAction(action_callback, veto_callback,
                veto_line, veto_terms, delay, *args))
            self.admin('(You may veto within %s seconds.)', num2name(delay))
        else: action_callback(*args)
    
    # Sending messages
    def send_hello(self, client):
        country = client.country
        if country: passcode = self.players[country].passcode
        else: country = UNO; passcode = 0
        variant = self.options.get_params()
        client.send(HLO(country, passcode, variant))
    def summarize(self):
        ''' Sends the end-of-game SMR message.'''
        players = self.summary
        for country, player in self.players.iteritems():
            stats = [
                country,
                [player.name or '""'],
                [player.version or ' '],
                self.judge.score(country)
            ]
            elim = self.judge.eliminated(country)
            if elim: stats.append(elim)
            players.append(stats)
        return SMR(self.judge.turn(), *players)
    def broadcast(self, message):
        ''' Sends a message to each ready client, and notes it in the log.'''
        self.log_debug(2, 'ALL << %s', message)
        for client in self.clients: client.write(message)
    def broadcast_list(self, message_list):
        ''' Sends a list of messages to each ready client'''
        for msg in message_list: self.broadcast(msg)
    def admin(self, line, *args):
        if self.server.options.snd_admin:
            self.broadcast(ADM('Server', str(line) % args))
    
    # Press and administration
    def send_listing(self, client):
        client.send(LST(self.game_id, self.players_needed(),
            self.variant.variant, self.options.get_params()))
    def handle_GOF(self, client, message):
        country = client.country
        if country and self.judge.phase:
            self.players[country].ready = True
            client.accept(message)
            missing = self.judge.missing_orders(country)
            if missing: client.send(missing)
        else: client.reject(message)
    def handle_SND(self, client, message):
        ''' Sends the press message to the recipients,
            subject to various caveats listed in the syntax document.
        '''#'''
        from validation import trimmed
        
        country = client.country
        eliminated = self.judge.eliminated()
        if country and self.press_allowed and country not in eliminated:
            folded = message.fold()
            recips = folded[2]
            for nation in recips:
                if not self.players[nation].client:
                    client.send(CCD(nation))
                    break
                elif nation in eliminated:
                    client.send(OUT(nation))
                    break
            else:
                msg_id = (country, folded[1][0])
                press = Message(folded[3:])
                # Send OUT if any power in press is eliminated
                for nation in eliminated:
                    if nation in press:
                        client.send(OUT(nation))
                        return
                # Trim high-level tokens from TRY messages
                for token,level in trimmed.items():
                    if level > self.options.LVL:
                        while token in press:
                            press.remove(token)
                outgoing = FRM(msg_id, recips)
                outgoing.extend(press)
                for nation in recips:
                    self.players[nation].client.send(outgoing)
                client.accept(message)
        else: client.reject(message)
    def handle_HLO(self, client, message):
        if self.started: self.send_hello(client)
        else: client.reject(message)
    def handle_TME(self, client, message):
        if self.deadline: remain = self.deadline - time()
        else: remain = 0
        
        if len(message) == 1:
            # Request for amount of time left in the turn
            if remain: client.send(TME(relative_limit(remain)))
            else:      client.reject(message)
        elif len(message) == 4 and message[2].is_integer():
            request = absolute_limit(message[2].value())
            if request > max(self.limits.values()):
                # Ignore requests greater than the longest time limit
                client.reject(message)
            else:
                # Add it to the list
                self.timers.setdefault(request, []).append(client)
                client.accept(message)
        else: client.reject(message)
    
    # Messages with standard prefixes
    def handle_NOT_TME(self, client, message):
        ''' Cancels client timer requests.
            NOT (TME) cancels all requests, NOT (TME (seconds)) just one.
        '''#'''
        reply = YES
        if len(message) == 4: self.cancel_time_requests(client)
        elif message[4].is_integer():
            # Remove the request from the list, if it's there.
            try: self.timers[absolute_limit(message[4].value())].remove(client)
            except (ValueError, KeyError): reply = REJ
        else: reply = REJ
        client.send(reply(message))
    def handle_NOT_GOF(self, client, message):
        country = client.country
        if country and self.judge.phase and not self.judge.eliminated(country):
            self.players[country].ready = False
            client.accept(message)
        else: client.reject(message)
    def handle_YES_MAP(self, client, message):
        if message.fold()[1][1][0].lower() == self.judge.map_name:
            if client in self.clients: return # Ignore duplicate messages
            self.clients.append(client)
            if self.server.options.admin_cmd:
                client.admin('Welcome.  This server accepts admin commands; '
                        'send "Server: help" for details.')
            name = client.full_name()
            obs = ''
            if client.country:
                self.players[client.country].ready = True
            else:
                if client.name: obs = ' as an observer'
                if self.started: self.reveal_passcodes(client)
            self.admin('%s has connected%s. %s', name, obs, self.has_need())
            
            if self.started:
                self.send_hello(client)
                # This should probably be farmed out to the judge,
                # but it works for now.
                client.send(self.judge.map.create_SCO())
                client.send(self.judge.map.create_NOW())
                if self.closed:
                    msg = self.judge.game_end
                    if msg: client.send(msg)
                    client.send(self.summarize())
            else: self.check_start()
        else: client.reject(message); self.disconnect(client)
    def handle_REJ_MAP(self, client, message): self.disconnect(client)
    def handle_YES_SVE(self, client, message): pass
    def handle_REJ_SVE(self, client, message): pass
    def handle_YES_LOD(self, client, message): pass
    def handle_REJ_LOD(self, client, message): self.disconnect(client)
    
    # Identity messages
    def handle_NME(self, client, message):
        if self.started or client.country:
            # Prohibit playing multiple positions,
            # and block signups after starting a game
            client.reject(message)
            self.reveal_passcodes(client)
            if not client.name:
                msg = message.fold()
                client.name = msg[1][0]
                client.version = msg[2][0]
        else:
            for country in self.p_order:
                # Take the first open slot
                if not self.players[country].client:
                    self.offer_power(country, client, message)
                    break
            else:
                # Wait for an opening
                self.log_debug(6, 'Leaving client #%d in limbo', client.client_id)
                self.limbo[client] = message
    def handle_IAM(self, client, message):
        country = message[2]
        passcode = message[5].value()
        self.log_debug(9, 'Considering IAM (%s) (%d)', country, passcode)
        slot = self.players[country]
        
        # Block attacks by the unscrupulous.
        if not self.started:
            # Check whether we have actually given out this passcode
            if slot.assigned and slot.passcode == passcode:
                self.log_debug(6, 'Client #%d takes over %s', client.client_id, country)
                old_client = slot.client
                if old_client:
                    for new_country in self.p_order:
                        # Take the first open slot
                        new_slot = self.players[new_country]
                        if not new_slot.client:
                            self.log_debug(6, 'Reassigning client #%d to %s',
                                    old_client.client_id, new_country)
                            old_client.country = new_country
                            new_slot.copy_client(slot)
                            break
                    else:
                        self.log_debug(1, 'No place to put old client #%d!',
                                old_client.client_id)
                        old_client.country = None
                
                slot.new_client(client, True)
                client.country = country
                client.accept(message)
            else:
                client.reject(message)
                if client.country: self.open_position(country)
                client.boot()
        elif client.guesses < 3 and slot.passcode == passcode:
            # Be very careful here.
            old_client = slot.client
            self.log_debug(9, 'Passcode check succeeded; switching from %r', client.country)
            
            if old_client is client and country == client.country:
                # It's already okay.
                good = False
            elif not old_client:
                # Allow taking over empty slots, but not by existing players
                good = not client.country
                if good: self.broadcast(NOT(CCD(country)))
            elif self.server.options.takeovers:
                # The current client might be dead, but we haven't noticed yet.
                # Or this could be a legitimate GM decision,
                # to replace a bot with a human player
                good = True
            else: good = False
            
            if good:
                self.log_debug(6, 'Client #%d takes control of %s', client.client_id, country)
                if client not in self.clients: self.clients.append(client)
                if client.country: self.open_position(client.country)
                client.country = country
                if (client.name and self.server.options.replaced and
                        (slot.name, slot.version) !=
                        (client.name, client.version)):
                    # Slight abuse of the syntax:
                    # Replaced players are reported, with the year of
                    # replacement and their center count at that time.
                    # This means the country will be reported multiple times.
                    self.summary.append([
                        country,
                        [slot.name or '""'],
                        [slot.version or ' '],
                        self.judge.score(country),
                        self.judge.turn().year
                    ])
                slot.new_client(client)
                slot.ready = True
                client.accept(message)
                if old_client: old_client.boot()
                
                # Restart timers if everybody's here
                unready = self.players_unready()
                if unready: self.log_debug(9, 'Still waiting for %s', expand_list(unready))
                elif self.time_left: self.set_deadlines(self.time_left)
            else: client.reject(message)
        else:
            self.log_debug(7, 'Passcode check failed')
            client.guesses += 1
            client.reject(message)
    def handle_OBS(self, client, message):
        if client in self.clients: client.reject(message)
        else:
            if len(message) > 1:
                msg = message.fold()
                client.name, client.version = (msg[1][0], msg[2][0])
            client.send_list([YES(message), MAP(self.judge.map_name)])
    
    # Game-specific admin commands
    def find_players(self, name):
        result = []
        low_result = []
        for key, struct in self.players.iteritems():
            names = (struct.name, struct.version)
            if self.started: names += (struct.pname, key.text)
            for item in names:
                if name == item:
                    result.append((struct.client, item))
                elif name == item.lower():
                    low_result.append((struct.client, item))
        return result or low_result
    def eject(self, client, match):
        verb, name = match.groups()
        players = self.find_players(name)
        if (len(players) == 1) or (players and not self.started):
            if verb == 'boot':
                veto_action = self.block_boot
                veto_verb = 'booting'
                terms = ('boot', 'booting')
            else:
                veto_action = None
                veto_verb = 'ejection'
                terms = ('eject', 'ejection')
            
            names = DefaultDict(0)
            for c,n in players: names[n] += 1
            itemlist = [(num,nam) for nam,num in names.items()]
            itemlist.sort()
            self.queue_action(client, self.boot_players,
                    '%sing %s from the game.' %
                    (verb, expand_list([instances(num, nam, False)
                        for num,nam in itemlist])),
                    veto_action, 'the player %s.' % veto_verb, terms,
                    [c for c,n in players])
        else:
            status = players and 'Ambiguous' or 'Unknown'
            client.admin('%s player "%s"', status, name.capitalize())
    def block_boot(self, client, players):
        if client in players: return "You can't veto your own booting."
    def boot_players(self, players):
        for client in players: client.boot()
    def list_players(self, client, match):
        players = []
        observers = []
        observing = 0
        for person in self.clients:
            if person.name:
                name = '  ' + person.full_name()
                if person.country: players.append(name)
                else: observers.append(name)
            else: observing += 1
        if players:
            client.admin('Players:')
            players.sort()
            for line in players: client.admin(line)
        if observers:
            client.admin('Observers:')
            observers.sort()
            for line in observers: client.admin(line)
        if observing:
            client.admin('%s anonymous observer%s',
                    num2name(observing).capitalize(), s(observing))
    def stop_time(self, client, match):
        if self.paused: client.admin('The game is already paused.')
        else:
            self.pause()
            self.admin('%s has paused the game.', client.full_name())
    def resume(self, client, match):
        if self.paused:
            self.paused = False
            if self.time_left: self.set_deadlines(self.time_left)
            self.admin('%s has resumed the game.', client.full_name())
        else: client.admin('The game is not currently paused.')
    def start_bot(self, client, match):
        ''' Starts the specified number of the specified kind of bot.
            If number is less than one, it will be added to
            the number of empty power slots in the client's game.
        '''#'''
        if self.num_players() < self.server.options.bot_min:
            #client.admin('This server is not designed for solo games;')
            client.admin('Recruit more players first, or use your own bots.')
            return
        bot_name = match.group(2)
        if bot_name[-1] == 's' and not bots.has_key(bot_name):
            bot_name = bot_name[:-1]
            default_num = 0
        else: default_num = 1
        if bots.has_key(bot_name):
            bot_class = bots[bot_name]
            country = match.group(3)
            if country:
                for token, struct in self.players.items():
                    if country in (token.text.lower(), struct.pname.lower()):
                        num = 1
                        power = token
                        pcode = struct.passcode
                        pname = struct.pname
                        if self.started and struct.client and not struct.client.closed:
                            client.admin('%s is still in the game.', pname)
                            return
                        else: struct.assigned = (bot_class.name, bot_class.version)
                        break
                else:
                    client.admin('Unknown player: %s', country)
                    return
            else:
                power = pcode = None
                try: num = int(match.group(1))
                except TypeError: num = default_num
                if num < 1: num += self.players_needed()
            
            name = bot_class.name
            self.queue_action(client, self.start_bot_class, 'starting %s%s.' %
                    (instances(num, name), power and ' as %s' % pname or ''),
                    None, 'the %s%s.' % (name, s(num)),
                    ('start', 'bot', 'bots', name, name + 's'),
                    bot_class, num, power, pcode)
        else: client.admin('Unknown bot: %s', bot_name)
    def start_bot_class(self, bot_class, number, power, pcode):
        # Client.open() needs to be in a separate thread from the polling
        self.log_debug(11, 'Attempting to start %s %s%s',
                num2name(number), bot_class.name, s(number))
        def callback(success, failure):
            if failure:
                self.admin('%s bot%s failed to start',
                        num2name(failure).capitalize(), s(failure))
        self.server.manager.async_start(bot_class, number, callback,
                game_id=self.game_id, power=power, passcode=pcode)
    def num_players(self):
        from sets import Set
        return len(Set([p.client.address
            for p in self.players.values() if p.client]))
    def set_press_level(self, client, match):
        cmd, specific, level = match.groups()
        if specific:
            try: new_level = config.press_levels[level]
            except KeyError:
                client.admin('Invalid press level %r', level.capitalize())
                return
        elif cmd == 'en': new_level = 8000
        elif cmd == 'dis': new_level = 0
        old_level = self.options.LVL
        if new_level == old_level:
            client.admin('The press level is already %d', old_level)
        elif self.started:
            client.admin('The press level can only be changed before the game starts.')
        else:
            self.options.LVL = new_level
            self.admin('%s has set the press level to %d (%s).',
                    client.full_name(), new_level,
                    config.press_levels[new_level])
    def end_game(self, client, match):
        if self.closed: client.admin('The game is already over.')
        else:
            self.queue_action(client, self.close, 'ending the game.',
                    None, 'ending the game.', ('end', 'close'))
    def veto_admin(self, client, match):
        word = match.group(2)
        if word: actions = [a for a in self.actions if word in a.terms]
        else: actions = list(self.actions)
        if actions:
            for vetoed in actions: vetoed.veto(client)
        else:
            client.admin('%s to %s.', match.group(1),
                word and ('No %s commands' % word) or 'Nothing')
    
    commands = [
        Command(r'who|list players', list_players,
            '  list players - Lists the player names (but not power assignments)'),
        Command(r'(veto|cancel|reject) *(\w*)', veto_admin,
            '  veto [<command>] - Cancels recent admin commands'),
        Command(r'(en|dis)able +press *(level +(\d+|[a-z ]+))?', set_press_level,
            '  enable/disable press - Allows or blocks press between powers'),
        Command(r'pause', stop_time,
            '  pause - Stops deadline timers and phase transitions'),
        Command(r'resume|unpause', resume,
            '  resume - Resumes deadline timers and phase transitions'),
        Command(r'(eject|boot) +(.+)', eject,
            '  eject <player> - Disconnect <player> (either name or country) from the game'),
        Command(r'end game', end_game,
            '  end game - Ends the game (without a winner)'),
        Command(r'start (an? )?(\w+) as (\w+)', start_bot,
            '  start <bot> as <country> - Start a copy of <bot> to play <country>'),
        Command(r'start (an? |\d+ )?(\w+)()', start_bot,
            '  start <number> <bot> - Invites <number> copies of <bot> into the game'),
    ]


class Judge(Verbose_Object):
    ''' The Arbitrator of Justice and Keeper of the Official Map.
        This class has the minimum skeleton required by the Server.
        
        Flags for the server:
            - unready:  True until each power has a set of valid orders.
            - phase:    Indicates the phase of the current turn.
            - game_end: The message indicating how the game ended, if it has.
        
        phase will be a Turn.phase() result for a game in progress,
        None for games ended or not yet started.
    '''#'''
    
    def __init__(self, variant_opts, game_opts):
        ''' Initializes instance variables.'''
        self.map = Map(variant_opts)
        assert self.map.valid
        self.mdf = variant_opts.map_mdf
        self.map_name = variant_opts.map_name
        self.game_opts = game_opts
        self.game_end = None
        self.unready = True
        self.phase = None
    def reset(self):
        ''' Prepares the judge to begin a fresh game with the same map.
        '''#'''
        self.unready = True
        self.phase = None
        self.map.restart()
    def start(self):
        ''' Starts the game, returning NOW and SCO messages.'''
        raise NotImplementedError
    def run(self):
        ''' Process orders, whether or not the powers are all ready.
            Returns applicable ORD, NOW, and SCO messages.
            At the end of the game, returns SLO/DRW and SMY messages.
        '''#'''
        raise NotImplementedError
    
    # Interaction with players
    def handle_MAP(self, client, message): client.send(MAP(self.map_name))
    def handle_MDF(self, client, message): client.send(self.mdf)
    def handle_NOW(self, client, message): raise NotImplementedError
    def handle_SCO(self, client, message): raise NotImplementedError
    def handle_ORD(self, client, message): raise NotImplementedError
    def handle_HST(self, client, message): raise NotImplementedError
    def handle_SUB(self, client, message): raise NotImplementedError
    def handle_DRW(self, client, message): raise NotImplementedError
    def handle_MIS(self, client, message): raise NotImplementedError
    def handle_NOT_SUB(self, client, message): raise NotImplementedError
    def handle_NOT_DRW(self, client, message): raise NotImplementedError
    
    # Law of Demeter
    def missing_orders(self, country): raise NotImplementedError
    def players(self): return self.map.powers.keys()
    def player_name(self, country): return self.map.powers[country].name
    def score(self, player): return len(self.map.powers[player].centers)
    def turn(self): return self.map.current_turn
    def eliminated(self, country=None):
        ''' Returns the year the power was eliminated,
            or False if it is still in the game.
            Without a country, returns a list of eliminated countries.
        '''#'''
        raise NotImplementedError
