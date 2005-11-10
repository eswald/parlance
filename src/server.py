import config, re
from random    import randint, shuffle
from time      import time
from gameboard import Turn
from functions import any, s, expand_list, Verbose_Object
from language  import *

import player, evilbot, dumbbot
bots = {
    'holdbot': player.HoldBot,
    'dumbbot': dumbbot.DavidBot,
    'dumberbot': dumbbot.DumbBot,
    'evilbot': evilbot.EvilBot,
}

class main_options(config.option_class):
    ''' Options used to start clients and the server, including:
        - verbosity    How much debug or logging information to display
        - internal     Whether to start the internal server
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
        self.internal    = self.getboolean('use internal server', False)
        self.verbosity   = self.getint('output verbosity', 1)
class server_options(config.option_class):
    ''' Options for the server, including:
        - robin        Whether to conduct round-robin tournaments
        - takeover     Whether to allow taking over an existing power
        - snd_admin    Whether to send admin messages created by the server
        - fwd_admin    Whether to send admin messages from other players
        - games        Number of games to play
    '''#'''
    section = 'server'
    def __init__(self):
        self.robin     = self.getboolean('round-robin',            False)
        self.takeover  = self.getboolean('allow takeovers',        False)
        self.snd_admin = self.getboolean('send admin messages',    False)
        self.fwd_admin = self.getboolean('forward admin messages', False)
        self.quit      = self.getboolean('close on disconnect',    False)
        self.variant   = self.getstring( 'variant name',           'standard')
        self.games     = self.getint(    'number of games',        1)


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
    
    password = '_now34'
    
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
        self.start_game()
    
    def deadline(self):
        now = time()
        time_left = [game.max_time(now) for game in self.games if game.deadline]
        if time_left: return max([0, min(time_left)])
        elif any(self.games, lambda x: not x.closed): return None
        else: return 0
    def check(self):
        open_games = [game for game in self.games if not game.closed]
        if open_games:
            for game in open_games: game.check_flags()
        elif 0 < self.options.games <= len(self.games):
            self.log_debug(11, 'Completed all requested games')
            self.close()
        else: self.start_game()
    
    def broadcast_admin(self, text):
        if self.options.snd_admin: self.broadcast(ADM('Server', text))
    
    def handle_message(self, client, message):
        'Processes a single message from any client.'
        reply = message.validate(client.country, client.game.options.LVL)
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
                client.send(HUH(message))
    def handle_ADM(self, client, message):
        text = message.fold()[2][0].lower()
        if text[0:7] == 'server:':
            for pattern in self.commands:
                match = pattern['pattern'].search(text, 7)
                if match:
                    pattern['command'](self, client, match)
                    break
            else:
                for pattern in client.game.commands:
                    match = pattern['pattern'].search(text, 7)
                    if match:
                        if client.mastery:
                            pattern['command'](client.game, client, match)
                        else:
                            client.admin('You are not authorized to do that.')
                        break
                else: client.admin('Unrecognized command: "%s"', text[7:])
        elif self.options.fwd_admin:
            if text[0:4] == 'all:': self.broadcast(message)
            else: client.game.broadcast(message)
        else: client.reject(message)
    def handle_SEL(self, client, message):
        if len(message) > 3:
            reply = self.join_game(client, message[2].value()) and YES or REJ
            client.send(reply(message))
            return True
        return False
    def handle_PNG(self, client, message): client.accept(message)
    
    def default_game(self):
        games = list(self.games)
        games.reverse()
        for game in games:
            if not game.closed: return game
        else: return self.start_game()
    def join_game(self, client, game_id):
        if client.game.game_id != game_id < len(self.games):
            client.game.disconnect(client)
            client.game = self.games[game_id]
            return True
        else: return False
    def start_game(self, client=None, match=None):
        if match and match.lastindex:
            var_name = match.group(1)
            try: variant = config.variant_options(var_name)
            except:
                client.admin('Unknown variant "%s"', var_name)
                return
        else: variant = config.variant_options(self.options.variant)
        game_id = len(self.games)
        if client: client.admin('New game started, with id %s.', game_id)
        game = Game(self, game_id, variant)
        self.games.append(game)
        self.manager.start_clients()
        return game
    def select_game(self, client, match):
        try: num = int(match.group(1))
        except ValueError:
            client.admin('The game_id must be an integer.')
        else:
            if self.join_game(client, num):
                client.admin('Joined game #%d.', num)
            else: client.admin('Unknown game #%d.', num)
    def list_variants(self, client, match): client.admin('Command accepted.')
    def list_help(self, client, match):
        for line in ([
            #'Begin an admin message with "All:" to send it to all players, not just the ones in the current game.',
            'Begin an admin message with "Server:" to use the following commands, all of which are case-insensitive:',
        ] + [pattern['decription'] for pattern in self.commands]):
            client.admin(line)
    def list_master(self, client, match):
        preface = client.mastery and 'As the game master, you may' or 'If you were the game master, you could'
        client.admin('%s begin an admin message with "Server:" to use the following commands:', preface)
        for line in [pattern['decription'] for pattern in client.game.commands]:
            client.admin(line)
    def close(self, client=None, match=None):
        ''' Tells clients to exit, and closes the server's sockets.'''
        if client:
            if match.group(1) == self.password:
                self.broadcast_admin('The server has been killed.  Good-bye.')
            else:
                client.admin('Password incorrect.  Good-bye.')
                client.boot()
                return
        if not self.closed:
            self.log_debug(10, 'Closing')
            self.broadcast(OFF())
            #self.__super.close()
            self.closed = True
            self.manager.close_threads()
            self.log_debug(11, 'Done closing')
        else: self.log_debug(11, 'Duplicate close() call')
    def become_master(self, client, match):
        if client.mastery: client.admin('You are already a game master.')
        elif client.guesses < 3 and match.group(1) == self.password:
            client.mastery = True
            client.admin('Master powers granted.')
        else:
            client.admin('Password incorrect.')
            client.guesses += 1
    
    commands = [
        {'pattern': re.compile('new game'), 'command': start_game,
        'decription': '  new game - Starts a new game of Standard Diplomacy'},
        #{'pattern': re.compile('new (\w+) game'), 'command': start_game,
        #'decription': 'new <variant> game - Starts a new game of <variant>'},
        #{'pattern': re.compile('select game #?(\w+)'), 'command': select_game,
        #'decription': '  select game <id> - Switches to game <id>, if it exists'},
        #{'pattern': re.compile('help variants'), 'command': list_variants,
        #'decription': '  help variants - Lists known variants'},
        {'pattern': re.compile('master (\w+)'), 'command': become_master,
        'decription': '  master <password> - Grants you power to use master commands'},
        {'pattern': re.compile('help master'), 'command': list_master,
        'decription': '  help master - Lists commands that a game master can use'},
        {'pattern': re.compile('help'), 'command': list_help,
        'decription': '  help - Lists admin commands recognized by the server'},
        {'pattern': re.compile('shutdown (\w+)'), 'command': close,
        #'decription': '  shutdown <password> - Stops the server'},
        'decription': ' '},
    ]


class Game(Verbose_Object):
    ''' Coordinates messages between Players and the Judge,
        administering time limits and power assignments.
        
        Note: This implementation accepts press and other messages after
        the deadlines, until network traffic stops.  That prevents mass
        amounts of last-second traffic from preventing someone's orders
        from going through, but can be abused.
    '''#'''
    
    def __init__(self, server, game_id, variant):
        ''' Initializes the plethora of instance variables:
            
            # Configuration and status information
            - server           The overarching server for the program
            - game_id          The unique identification for this game
            - options          The game_options instance for this game
            - judge            The judge, handling orders and adjudication
            - press_allowed    Whether press is allowed right now
            - started     Whether the game has started yet
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
        self.representation = variant.rep
        
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
        
        move_limit = self.absolute_limit(game.MTL)
        press_limit = self.absolute_limit(game.PTL)
        build_limit = self.absolute_limit(game.BTL)
        retreat_limit = self.absolute_limit(game.RTL)
        self.press_in = {
            Turn.move_phase    : press_limit < move_limit or not move_limit,
            Turn.retreat_phase : not retreat_limit,
            Turn.build_phase   : not build_limit,
        }
        
        self.limits = {
            None               : 0,
            Turn.move_phase    : move_limit,
            Turn.retreat_phase : retreat_limit,
            Turn.build_phase   : build_limit,
            'press'            : press_limit,
        }
        
        self.clients        = []
        self.masters        = []
        self.players        = {}
        self.limbo          = {}
        powers = self.judge.players()
        shuffle(powers)
        self.p_order        = powers
        bound = Token.opts.max_pos_int
        for country in powers:
            self.players[country] = {
                'client'   : None,
                'passcode' : randint(100, bound-1),
                'name'     : '',
                'version'  : '',
                'ready'    : False,
                'pname'    : self.judge.player_name(country),
            }
    def prefix(self): return 'Game %d' % self.game_id
    prefix = property(fget=prefix)
    
    # Connecting and disconnecting players
    def open_position(self, country):
        ''' Frees the player slot to be taken over,
            and either broadcasts the CCD message (during a game),
            or tries to give it to the oldest client in limbo.
        '''#'''
        player = self.players[country]
        player['client'] = None
        player['ready'] = True
        if self.closed: pass
        elif self.judge.phase:
            self.broadcast(CCD(country))
            pcode = 'Passcode for %s: %d' % (player['pname'], player['passcode'])
            self.log_debug(6, pcode)
            if not self.judge.eliminated(country):
                for client in self.clients:
                    if client.mastery: client.admin(pcode)
                if self.options.DSD: self.pause()
        elif self.limbo: self.offer_power(country, *self.limbo.popitem())
    def offer_power(self, country, client, message):
        ''' Sets the client as the player for the power,
            pending acceptance of the map.
        '''#'''
        self.log_debug(6, 'Offering %s to client #%d', country, client.client_id)
        client.send_list([YES(message), MAP(self.judge.map_name)])
        msg = message.fold()
        client.country = country
        slot = self.players[country]
        slot['name']    = name    = msg[1][0]
        slot['version'] = version = msg[2][0]
        slot['client']  = client
        slot['ready']   = False
        slot['robotic'] = 'Human' not in name + version
    def players_unready(self):
        ''' A list of disconnected or unready players.'''
        return [country
            for country, struct in self.players.iteritems()
            if not ((struct['client'] and struct['ready']) or self.judge.eliminated(country))
        ]
    def disconnect(self, client):
        self.log_debug(6, 'Client #%d has disconnected', client.client_id)
        self.cancel_time_requests(client)
        opening = None
        if client in self.clients:
            self.clients.remove(client)
            if client.booted:
                player = self.players[client.booted]
                if player['client'] is client:
                    reason = 'booted'
                    opening = client.booted
                else: reason = 'replaced'
                name = player[self.started and 'pname' or 'name']
                self.admin('%s has been %s. %s', name, reason, self.has_need())
            elif client.country:
                player = self.players[client.country]
                if self.closed or not self.started:
                    self.admin('%s (%s) has disconnected. %s',
                            player['name'], player['version'], self.has_need())
                opening = client.country
                client.country = None
            else: self.admin('An Observer has disconnected. %s', self.has_need())
        elif client.country:
            # Rejected the map
            opening = client.country
            client.country = None
        elif self.limbo.has_key(client): del self.limbo[client]
        
        # For testing purposes: stop the game if a player quits
        if opening and not self.closed:
            self.log_debug(11, 'Deciding whether to quit (%s)',
                    self.server.options.quit)
            if self.server.options.quit: self.close()
            else: self.open_position(opening)
        
        # Pass on the role of game master, if necessary
        if client in self.masters: self.masters.remove(client)
        if self.masters and not (self.closed or any([c.mastery for c in self.clients])):
            master = self.masters[0]
            master.mastery = True
            master.admin('You have been granted master powers; send "Server: help master" to list them.')
    def close(self, client=None, match=None):
        self.log_debug(10, 'Closing')
        self.deadline = None
        self.judge.phase = None
        if not self.closed:
            self.closed = True
            if self.started: self.broadcast(self.summarize())
    def reveal_passcodes(self, client):
        disconnected = {}
        robotic = {}
        for country, player in self.players.iteritems():
            if not self.judge.eliminated(country):
                if not player['client']: disconnected[country] = player['passcode']
                elif player['robotic']: robotic[country] = player['passcode']
        msg = None
        slate = None
        if disconnected:
            if len(disconnected) > 1: msg = 'have been disconnected'
            else: msg = 'has been disconnected'
            slate = disconnected
        elif robotic:
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
        return len([p for p in self.players.itervalues() if not p['client']])
    def has_need(self):
        ''' Creates the line announcing connected and needed players.'''
        if self.closed: return ''
        observing = len([True for client in self.clients if not client.country])
        have      = len(self.clients) - observing
        needed    = len(self.players) - have
        need = ''
        if not self.started:
            if needed: need = 'Need %d to start.' % needed
            else: need = 'Game on!'
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
            self.broadcast(NOT(TME(self.relative_limit(self.time_left))))
        self.paused = True
    def absolute_limit(self, time_limit):
        ''' Converts a TME message number into a number of seconds.
            Negative message numbers indicate hours; positive, seconds.
        '''#'''
        if time_limit < 0: result = -time_limit * 3600
        else: result = time_limit
        return result
    def relative_limit(self, seconds):
        ''' Converts a number of seconds into a TME message number.
            Negative message numbers indicate hours; positive, seconds.
        '''#'''
        max_int = Token.opts.max_pos_int
        if seconds > max_int: result = -seconds // 3600
        else: result = seconds
        if -result > max_int: result = -max_int
        return result
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
            message = TME(self.relative_limit(seconds))
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
            Only valid if self.deadline is not None.
        '''#'''
        if self.ready(): return 0
        timers = [sec for sec in self.timers if sec < self.time_checked]
        timers.append(self.press_deadline and self.limits['press'] or 0)
        return (self.deadline - max(timers)) - now
    def cancel_time_requests(self, client):
        ''' Removes the client from the list of time requests.'''
        for client_list in self.timers.itervalues():
            while client in client_list: client_list.remove(client)
    def check_flags(self):
        ''' Checks deadlines, time requests, and wait flags,
            running the judge and sending notifications when appropriate.
        '''#'''
        if self.ready(): self.run_judge()
        elif self.deadline:
            now = time()
            remain = self.deadline - now
            for second in [sec for sec in self.timers if remain < sec < self.time_checked]:
                self.time_checked = second
                for client in self.timers[second]:
                    client.send(TME(self.relative_limit(second)))
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
        if self.judge.phase: self.set_deadlines()
        else: self.close()
    
    # Sending messages
    def send_hello(self, client):
        country = client.country
        if country: passcode = self.players[country]['passcode']
        else: country = OBS; passcode = 0
        variant = self.get_variant_list()
        client.send(HLO(country, passcode, variant))
    def get_variant_list(self):
        game = self.options
        variant = [(LVL, game.LVL)]
        if game.MTL: variant.append((MTL, self.relative_limit(game.MTL)))
        if game.RTL: variant.append((RTL, self.relative_limit(game.RTL)))
        if game.BTL: variant.append((BTL, self.relative_limit(game.BTL)))
        if game.AOA: variant.append((AOA,))
        if game.DSD: variant.append((DSD,))
        
        if game.LVL >= 10:
            if game.PDA: variant.append((PDA,))
            if game.NPR: variant.append((NPR,))
            if game.NPB: variant.append((NPB,))
            if game.PTL: variant.append((PTL, self.relative_limit(game.PTL)))
        return variant
    def summarize(self):
        ''' Sends the end-of-game SMR message.'''
        players = []
        for country, player in self.players.iteritems():
            stats = [
                country,
                [player['name']    or ' '],         # These must have a string.
                [player['version'] or ' '],
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
    def handle_GOF(self, client, message):
        country = client.country
        if country and self.judge.phase:
            self.players[country]['ready'] = True
            client.accept(message)
            missing = self.judge.missing_orders(country)
            if missing: client.send(missing)
        else: client.reject(message)
    def handle_SND(self, client, message):
        ''' Sends the press message to the recipients,
            subject to various caveats listed in the syntax document.
        '''#'''
        country = client.country
        if self.press_allowed and not self.judge.eliminated(country):
            folded = message.fold()
            recips = folded[2]
            for nation in recips:
                if not self.players[nation]['client']:
                    client.send(CCD(nation))
                    break
                elif self.judge.eliminated(nation):
                    client.send(OUT(nation))
                    break
            else:
                msg_id = (country, folded[1][0])
                press  = folded[3:]
                outgoing = FRM(msg_id, recips)
                outgoing.extend(press)
                for nation in recips:
                    self.players[nation]['client'].send(outgoing)
                client.accept(message)
        else: client.reject(message)
    def handle_MAP(self, client, message): client.send(MAP(self.judge.map_name))
    def handle_MDF(self, client, message): client.send(self.judge.mdf)
    def handle_HLO(self, client, message): self.send_hello(client)
    def handle_TME(self, client, message):
        if self.deadline: remain = self.deadline - time()
        else: remain = 0
        
        if len(message) == 1:
            # Request for amount of time left in the turn
            if remain: client.send(TME(self.relative_limit(remain)))
            else:      client.reject(message)
        elif len(message) == 4 and message[2].is_integer():
            request = self.absolute_limit(message[2].value())
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
            try: self.timers[self.absolute_limit(message[4].value())].remove(client)
            except (ValueError, KeyError): reply = REJ
        else: reply = REJ
        client.send(reply(message))
    def handle_NOT_GOF(self, client, message):
        country = client.country
        if country and self.judge.phase and not self.judge.eliminated(country):
            self.players[country]['ready'] = False
            client.accept(message)
        else: client.reject(message)
    def handle_YES_MAP(self, client, message):
        if message.fold()[1][1][0].lower() == self.judge.map_name:
            if client in self.clients: return # Ignore duplicate messages
            self.clients.append(client)
            if client.country:
                struct = self.players[client.country]
                struct['ready'] = True
                self.admin('%s (%s) has connected. %s',
                        struct['name'], struct['version'], self.has_need())
                if not struct['robotic']:
                    if not any([c.mastery for c in self.clients]):
                        client.mastery = True
                        client.admin('You have been granted master powers; send "Server: help master" to list them.')
                    self.masters.append(client)
            else:
                self.admin('An Observer has connected. %s', self.has_need())
                if self.started: self.reveal_passcodes(client)
            
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
        else:
            for country in self.p_order:
                # Take the first open slot
                if not self.players[country]['client']:
                    self.offer_power(country, client, message)
                    break
            else:
                # Wait for an opening
                self.log_debug(6, 'Leaving client #%d in limbo', client.client_id)
                self.limbo[client] = message
                #msg = message.fold()
    def handle_IAM(self, client, message):
        country = message[2]
        passcode = message[5].value()
        self.log_debug(9, 'Considering IAM (%s) (%d)', country, passcode)
        slot = self.players[country]
        
        # Block attacks by the unscrupulous.
        if not self.started:
            # They can't possibly know the passcodes legitimately
            client.reject(message)
            if client.country: self.open_position(country)
            client.boot()
        elif client.guesses < 3 and slot['passcode'] == passcode:
            # Be very careful here.
            old_client = slot['client']
            self.log_debug(9, 'Passcode check succeeded; switching from %r', client.country)
            
            if old_client is client and country == client.country:
                # It's already okay.
                good = False
            elif not old_client:
                # Allow taking over empty slots, but not by existing players
                good = not client.country
                if good: self.broadcast(NOT(CCD(country)))
            elif self.server.options.takeover:
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
                slot['client'] = client
                slot['ready'] = True
                slot['robotic'] = False # Assume a human is taking over
                slot['name'] += ' (taken over in %s)' % str(self.judge.turn())
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
        else: client.send_list([YES(message), MAP(self.judge.map_name)])
    
    # Commands for the master of a game
    def find_players(self, name):
        result = []
        low_result = []
        for key, struct in self.players.iteritems():
            names = (struct['name'], struct['version'])
            if self.started: names += (struct['pname'], key.text)
            
            if name in names:
                result.append(struct['client'])
            elif name.lower() in [n.lower() for n in names]:
                low_result.append(struct['client'])
        return result or low_result
    def eject(self, client, match):
        name = match.group(1)
        players = self.find_players(name)
        if len(players) == 1: players[0].boot()
        else:
            status = players and 'Ambiguous' or 'Unknown'
            client.admin('%s player "%s"', status, name)
    def stop_time(self, client, match):
        if self.paused: client.admin('The game is already paused.')
        else: self.pause(); client.admin('Game paused.')
    def resume(self, client, match):
        if self.paused:
            self.paused = False
            if self.time_left: self.set_deadlines(self.time_left)
            client.admin('Game resumed.')
        else: client.admin('The game is not currently paused.')
    def start_bot(self, client, match):
        ''' Starts the specified number of the specified kind of bot.
            If number is less than one, it will be added to
            the number of empty power slots in the client's game.
        '''#'''
        bot_name = match.group(2)
        default_num = 1
        if bot_name[-1] == 's' and not bots.has_key(bot_name):
            bot_name = bot_name[:-1]
            default_num = 0
        if bots.has_key(bot_name):
            try: num = int(match.group(1))
            except TypeError: num = default_num
            if num < 1: num += self.players_needed()
            # Client.open() needs to be in a separate thread from the polling
            def callback(success, failure):
                text = '%d bot%s started' % (success, s(success))
                if failure: text += '; %d bot%s failed to start' % (failure, s(failure))
                client.admin(text)
            self.server.manager.async_start(bots[bot_name],
                    num, callback, game_id=self.game_id)
        else: client.admin('Unknown bot: %s', bot_name)
    def list_bots(self, client, match):
        client.admin('Available types of bots:')
        for bot_class in bots.itervalues():
            client.admin('  %s - %s', bot_class.name, bot_class.description)
    def set_press_level(self, client, match):
        cmd = match.group(1)
        if cmd == 'en':    new_level = 8000
        elif cmd == 'dis': new_level = 0
        else:
            try: new_level = int(cmd)
            except ValueError:
                client.admin('Invalid press level "%s"', cmd)
                return
        self.options.LVL = new_level
        client.admin('Press level set to %d.', new_level)
    
    commands = [
        {'pattern': re.compile('(en|dis)able +press'), 'command': set_press_level,
        'decription': '  enable/disable press - Allows or blocks press between powers'},
        {'pattern': re.compile('pause'), 'command': stop_time,
        'decription': '  pause - Stops deadline timers and phase transitions'},
        {'pattern': re.compile('resume'), 'command': resume,
        'decription': '  resume - Resumes deadline timers and phase transitions'},
        {'pattern': re.compile('eject +(.+)'), 'command': eject,
        'decription': '  eject <player> - Disconnect <player> (either name or country) from the game'},
        {'pattern': re.compile('end game'), 'command': close,
        'decription': '  end game - Ends the game (without a winner)'},
        {'pattern': re.compile('start (an? |\d+ )?(\w+)'), 'command': start_bot,
        'decription': '  start <number> <bot> - Invites <number> copies of <bot> into the game'},
        {'pattern': re.compile('bots'), 'command': list_bots,
        'decription': '  bots - Lists bots that can be started'},
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
    
    def __init__(self, game_map, game_opts):
        ''' Initializes instance variables.'''
        assert game_map.valid
        self.map = game_map
        self.mdf = game_map.mdf()
        self.map_name = game_map.name
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
    def eliminated(self, country):
        ''' Returns the year the power was eliminated,
            or False if it is still in the game.
        '''#'''
        raise NotImplementedError

if __name__ == "__main__":
    from main import run_server
    run_server()

# vim: sts=4 sw=4 et tw=75 fo=crql1