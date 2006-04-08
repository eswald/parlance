''' PyDip client framework and simple clients
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
'''#'''

from __future__ import division

try: from threading import Thread
except ImportError: Thread = None

import config
from cPickle   import dump, load
from random    import randrange, shuffle
from functions import s, autosuper, Verbose_Object, version_string
from orders    import *

__version__ = "$Revision$"

class client_options(config.option_class):
    ''' Options for client behavior, including:
        - response      What to do when the Server sends something we don't understand
        - validate      Whether to check the syntax of incoming messages
        - confirm       Whether to send admin messages reporting order submission
    '''#'''
    section = 'clients'
    def __init__(self, player_class):
        self.response    = self.getstring('invalid message response', 'ignore').lower()
        self.validate    = self.getboolean('validate incoming messages', False)
        self.confirm     = self.getboolean('confirm order submission', False)
        functions = {
            int:  self.getint,
            str:  self.getstring,
            bool: self.getboolean,
            list: self.getlist,
        }
        for name,otype,text,default in player_class.options:
            setattr(self, name, functions[otype](text, default))

class Observer(Verbose_Object):
    ''' Just watches the game, declining invitations to join.'''
    # Magic variables:
    name = None        # Set this to a string for all subclasses.
    version = None     # Set this to a string to allow registration as a player.
    description = None # Set this to a string to allow use as a bot.
    options = ()       # Set of tuples: (name, type, config text, default)
    
    def __init__(self, send_method, representation, game_id=None, **kwargs):
        ''' Initializes the instance variables.'''
        self.client_opts = client_options(self.__class__)
        self.send_out = send_method      # A function that accepts messages
        self.rep      = representation   # The representation message
        self.closed   = False  # Whether the connection has ended, or should end
        self.map      = None   # The game board
        self.saved    = {}     # Positions saved from a SVE message
        self.opts     = None   # The variant options for the current game
        self.use_map  = False  # Whether to initialize a Map; saves time for simple observers
        self.quit     = True   # Whether to close immediately when a game ends
        self.power    = None
        
        # A list of variables to remember across SVE/LOD
        self.remember = ['map']
        
        # A list of message handlers that should be called in parallel.
        self.threaded = []
        
        # Register with the server
        if game_id is None: self.send_identity()
        else: self.send(SEL(game_id))
    def close(self): self.closed = True
    
    # Sending messages to the Server
    def send(self, message):
        if not self.closed: self.send_out(Message(message))
    def send_list(self, message_list):
        'Sends a list of Messages to the server.'
        for msg in message_list: self.send(msg)
    def send_admin(self, text, *args):
        self.send(ADM(self.name or 'Observer')(str(text) % args))
    def accept(self, message): self.send(YES(message))
    def reject(self, message): self.send(REJ(message))
    
    # Handling messages from the server
    def handle_message(self, message):
        ''' Process a new message from the server.
            Hands it off to a handle_XXX() method,
            where XXX is the first token of the message,
            if such a method is defined.
            
            Generally, message handling is sequential; that is,
            the event loop will wait for one message handler to finish
            before starting a new one.  Message handlers may start new threads
            to change this behavior.
        '''#'''
        self.log_debug(5, '<< %s', message)
        
        if self.client_opts.validate:
            # Check message syntax
            level = self.opts and self.opts.LVL or 0
            if message[0] is HLO:
                try: level = message[message.index(LVL) + 1].value()
                except (ValueError, IndexError): level = 0
            reply = message.validate(level, True)
        else: reply = None
        if reply:
            self.handle_invalid(message, reply=reply)
        else:
            # Note that try: / except AttributeError: doesn't work below,
            # because the method calls might produce AttributeErrors.
            method_name = 'handle_' + message[0].text
            
            # Special handling for common prefixes
            if message[0] in (YES, REJ, NOT, HUH):
                method_name += '_' + message[2].text
            self.log_debug(15, 'Searching for %s() methods', method_name)
            
            # Call map handlers first
            if self.map:
                method = getattr(self.map, method_name, None)
                if method: self.apply_handler(method, message)
            
            # Then call client handlers
            method = getattr(self, method_name, None)
            if method:
                if Thread and method_name in self.threaded:
                    Thread(target=self.apply_handler,
                            args=(method, message)).start()
                else: self.apply_handler(method, message)
        self.log_debug(12, 'Finished %s message', message[0])
    def apply_handler(self, method, message):
        self.log_debug(12, 'Calling %s', method)
        try: method(message)
        except Exception, e: self.handle_invalid(message, error=e)
    def handle_invalid(self, message, error=None, reply=None):
        response = self.client_opts.response
        if response in ('print', 'warn', 'carp', 'croak'):
            if error: self.log_debug(1, 'Error processing command: ' + str(message))
            else:     self.log_debug(1, 'Invalid server command: '   + str(message))
        if (response in ('huh', 'complain', 'carp', 'croak')
                and ERR not in message):
            self.send(reply or HUH(ERR + message))
        if response in ('die', 'close', 'carp', 'croak'): self.close()
        if error and response not in ('print', 'close', 'huh', 'carp', 'ignore'): raise
    
    # Starting the game
    def send_identity(self):
        ''' Registers the observer with the server.
            Uses name and version if it has them.
        '''#'''
        if self.name and self.version:
            self.send(OBS(self.name)(self.version))
        else: self.send(OBS)
    def handle_HUH_OBS(self, message):
        ''' The server didn't like our OBS ('name') ('version') message.'''
        self.send(OBS)
    def handle_HUH_SEL(self, message): self.send_identity()
    def handle_YES_SEL(self, message): self.send_identity()
    def handle_REJ_SEL(self, message):
        if self.quit: self.close()
    def handle_HLO(self, message):
        self.opts = config.game_options(message)
    
    # Automatic map handling
    def handle_MAP(self, message):
        ''' Handles the MAP command, creating a new map if possible.
            Sends MDF for unknown maps, YES for valid.
        '''#'''
        if self.use_map:
            from gameboard import Map
            mapname = message.fold()[1][0]
            variant = config.variants.get(mapname)
            if not variant:
                variant = config.variant_options(mapname, mapname, {}, self.rep)
                config.variants[mapname] = variant
            self.map = Map(variant)
            if self.map.valid:
                self.accept(message)
                if self.power: self.send_list([HLO, SCO, NOW])
            else: self.send(MDF)
        else: self.accept(message)
    def handle_MDF(self, message):
        ''' Replies to the MDF command.
            The map should have loaded itself, but might not be valid.
        '''#'''
        if self.map:
            if self.map.valid:
                self.accept(MAP(self.map.name))
                if self.power: self.send_list([HLO, SCO, NOW])
            else: self.reject(MAP(self.map.name))
        else: raise ValueError, 'MDF before MAP'
    def phase(self): return self.map.current_turn.phase()
    
    # End of the game
    def handle_OFF(self, message): self.close()
    def game_over(self, message):
        if self.quit: self.close()
        else: self.in_game = False
    handle_DRW = game_over
    handle_SLO = game_over
    handle_SMR = game_over
    
    # Other generic handlers
    def handle_SVE(self, message):
        ''' Attempts to save everything named by self.remember.'''
        from copy import deepcopy
        try:
            game = {}
            for name in self.remember:
                try: value = deepcopy(getattr(self, name))
                except AttributeError: value = None
                game[name] = value
            self.saved[message.fold()[1][0]] = game
            self.accept(message)
        except: self.reject(message)
    def handle_LOD(self, message):
        ''' Restores attributes saved from a SVE message.'''
        game = message.fold()[1][0]
        if self.saved.has_key(game):
            self.__dict__.update(self.saved[game])
            #for (name, value) in self.saved[game]:
            #   setattr(self, name, value)
            if self.power: self.send(IAM(self.power)(self.pcode))
            else: self.accept(message)
        else: self.reject(message)
    def handle_PNG(self, message): self.accept(message)

class Player(Observer):
    ''' Generic Diplomacy player.
        This class contains methods useful for all players,
        but is designed to be subclassed.
        Handle messages from the server by defining a handle_XXX method,
        where XXX is the name of the first token in the message.
        This class defines handlers for the following:
            MAP, MDF, HLO, DRW, SLO, OFF, SVE, LOD
        Most of them do everything you will need,
        in combination with instance variables.
    '''#'''
    def __init__(self, *args, **kwargs):
        ''' Initializes the instance variables.'''
        self.__super.__init__(*args, **kwargs)
        self.in_game   = False # Whether the game is currently in progress
        self.submitted = False # Whether any orders have been submitted this turn
        self.press_tokens = [] # Tokens to be sent in a TRY message
        self.bcc_list  = {}    # Automatic forwarding setup: sent messages
        self.fwd_list  = {}    # Automatic forwarding setup: received messages
        self.press     = {}    # A list of messages received and sent
        self.draws     = []    # A list of acceptable draws
        
        # Overrides certain Observer settings
        self.use_map   = True
        self.remember += ['in_game', 'power', 'pcode',
                'bcc_list', 'fwd_list', 'press', 'draws']
        self.threaded += ['handle_NOW']
        
        # Usefully sent through keyword arguments
        self.power = kwargs.get('power')     # The power being played, or None
        self.pcode = kwargs.get('passcode')  # The passcode from the HLO message
    def close(self):
        self.__super.close()
        self.closed = True
    def prefix(self):
        if self.power: return '%s (%s)' % (self.__class__.__name__, self.power)
        else: return self.__class__.__name__
    prefix = property(fget=prefix)
    
    # Starting the game
    def send_identity(self):
        ''' Registers the player with the server.
            Should send OBS, NME, or IAM.
            Unless overridden, sends IAM with a valid power and passcode,
            NME with a valid name and version, OBS otherwise.
            If game_id is not None, sends a SEL (game_id) message first.
        '''#'''
        if self.power and self.pcode is not None:
            self.log_debug(7, 'Using power=%r, passcode=%r',
                    self.power, self.pcode)
            if isinstance(self.power, Token):
                # Internally started
                self.send(IAM(self.power)(self.pcode))
            else:
                self.power = self.rep.get(self.power)
                if self.power:
                    try: self.pcode = int(pcode)
                    except ValueError:
                        self.log_debug(1, 'Invalid passcode "%r"', pcode)
                        self.pcode = None
                else: self.log_debug(1, 'Invalid power %r', self.power)
                
                # Send name first, to get it into the server's records
                self.send(NME(self.name)(self.version))
        elif self.name and self.version:
            self.send(NME(self.name)(self.version))
        else: self.send(OBS)
    def handle_REJ_NME(self):
        if self.power and self.pcode is not None:
            self.send(IAM(self.power)(self.pcode))
        elif self.quit: self.close()
    def handle_YES_IAM(self, message):
        if not self.map: self.send(MAP)
    def handle_REJ_IAM(self, message):
        if self.quit: self.close()
    def handle_HLO(self, message):
        self.__super.handle_HLO(message)
        self.pcode = message[5]
        power = message[2]
        if power.is_power():
            self.power = self.map.powers[power]
        elif self.quit: self.close()
        self.in_game = True
    
    # Submitting orders and draw requests
    def handle_NOW(self, message):
        ''' Requests draws, and calls generate_orders() in a separate thread.'''
        if self.in_game and self.power:
            self.submitted = False
            self.orders = OrderSet(self.power)
            if self.draws: self.request_draws()
            if self.missing_orders(): self.generate_orders()
    def request_draws(self):
        current = set(self.map.current_powers())
        for power_set in self.draws:
            if power_set == current: self.send(DRW)
            elif self.opts.PDA and power_set <= current:
                self.send(DRW(power_set))
    def generate_orders(self):
        ''' Create and send orders.
            Warning: Take care to make this function thread-safe;
            in particular, it must not use global or class variables
            that it sets.
        '''#'''
        raise NotImplementedError
    
    def submit_set(self, orders):
        self.orders = orders
        sub = orders.create_SUB(self.power)
        if sub and self.in_game:
            if self.submitted: self.send(NOT(SUB))
            self.submitted = True
            self.send(sub)
            if (self.client_opts.confirm and not self.missing_orders()):
                self.send_admin('Submitted.')
    def submit(self, order):
        self.orders.add(order, self.power)
        self.submitted = True
        self.send(SUB(order))
    
    def missing_orders(self):
        return self.orders.missing_orders(self.phase(), self.power)
    def handle_MIS(self, message):
        if len(message) > 1:
            self.log_debug(7, 'Missing orders for %s: %s; expected %s',
                    self.power, message, self.missing_orders())
    def handle_THX(self, message):
        ''' Complains about rejected orders, and tries to fix some of them.'''
        folded = message.fold()
        result = folded[2][0]
        if result != MBV:
            self.log_debug(7, 'Invalid order for %s: %s', self.power, message)
            replacement = None
            if result != NRS:
                move_unit = folded[1][0]
                move_type = folded[1][1]
                if move_type in (MTO, SUP, CVY, CTO):
                    replacement = [move_unit, HLD]
                elif move_type == RTO and result != NMR:
                    replacement = [move_unit, DSB]
                elif move_type == BLD and result != NMB:
                    replacement = [self.power, WVE]
            if replacement:
                self.log_debug(8, 'Ordering %s instead', Message(replacement))
                self.send(SUB(replacement))
    
    # Press handling
    def handle_FRM(self, message):
        ''' Default press handler.
            Attempts to dispatch it to a handle_press_XXX message.
            Also forwards it, if automatic forwarding has been requested.
            Implements the suggested response for unhandled messages.
        '''#'''
        folded = message.fold()
        sender = folded[1][0]
        recips = folded[2]
        press  = folded[3]
        
        # Save it for future reference
        self.press.setdefault(sender,[]).append(message)
        
        # Forward it if requested, but avoid loops
        if self.fwd_list.has_key(sender) and press[0] != FRM:
            self.send_press(self.fwd_list[sender], FRM(sender)(recips)(press))
        
        # Pass it off to a handler method
        method_name = 'handle_press_' + press[0].text
        self.log_debug(15, 'Searching for %s() handlers', method_name)
        try: method = getattr(self, method_name)
        except AttributeError:
            # No handler found; return the standard response
            if press[0] not in (HUH, TRY) and ERR not in message:
                self.send_press(sender, HUH(ERR + press))
                self.send_press(sender, TRY(self.press_tokens))
        else:
            try: method(sender, press)
            except Exception, err:
                self.send_press(sender, HUH(press ++ ERR))
                self.log_debug(7, 'Exception in %s(%s, %s): %s',
                        method_name, sender, press, err)
    def send_press(self, recips, press):
        if not (self.in_game and self.power): return
        
        # Standardize inputs
        if not isinstance(recips, list): recips = [recips]
        
        # Forward, if requested
        for recipient in recips:
            if self.bcc_list.has_key(recipient) and press[0] != FRM:
                self.send_press(self.bcc_list[recipient],
                    FRM(self.power)(recips)(press))
        
        # Create and store the message
        message = SND(recips)(press)
        self.press.setdefault(self.power.key,[]).append(message)
        
        # Actually send the message
        self.send(message)


class HoldBot(Player):
    ''' A simple bot to hold units in position.'''
    name = 'HoldBot'
    version = version_string(__version__, name)
    description = 'Just holds its position'
    
    class Cycler:
        __slots__ = ('seq', 'index')
        def __init__(self, sequence):
            self.seq = list(sequence)
            shuffle(self.seq)
            self.index = 0
        def next(self):
            self.index += 1
            self.index %= len(self.seq)
            return self.seq[self.index]
    names = Cycler(('Ed', 'Ned', 'Ted', 'Jed', 'Zed', 'Red', 'Fred'))
    
    def __init__(self, *args, **kwargs):
        self.name = self.names.next()
        self.__super.__init__(*args, **kwargs)
    def handle_NOW(self, message):
        ''' Sends the commands to hold all units in place.
            Disbands units that must retreat.
            Waives any (unlikely) builds,
            and removes random units if necessary.
            Always requests a draw.
        '''#'''
        self.submitted = False
        if self.in_game and self.power:
            from gameboard import Turn
            self.send(DRW)
            orders = OrderSet(self.power)
            phase = self.map.current_turn.phase()
            self.log_debug(11, 'Holding %s in %s', self.power, self.map.current_turn)
            if phase == Turn.move_phase:
                for unit in self.power.units: orders.add(HoldOrder(unit))
            elif phase == Turn.retreat_phase:
                for unit in self.power.units:
                    if unit.dislodged: orders.add(DisbandOrder(unit))
            elif phase == Turn.build_phase:
                surplus = self.power.surplus()
                if surplus < 0: orders.waive(-surplus)
                elif surplus > 0:
                    units = self.power.units[:]
                    shuffle(units)
                    while surplus > 0:
                        surplus -= 1
                        orders.add(RemoveOrder(units.pop()))
            self.submit_set(orders)

class AutoObserver(Observer):
    ''' Just watches the game, declining invitations to join.'''
    
    admin_state = 0
    def handle_ADM(self, message):
        ''' Try to politely decline invitations,
            without producing too many false positives.
            
            >>> class Responder:
            ...     def __init__(self):
            ...         self.player = Echo(self.send_back, {})
            ...     def send_back(self, msg):
            ...         if msg[0] is ADM:
            ...             self.player.handle_ADM(msg)
            >>> p = Responder().player
            Echo: << OBS
            >>> p.handle_ADM(ADM('Server')('An Observer has connected. '
            ...     'Have 5 players and 1 observers. Need 2 to start'))
            >>> p.handle_ADM(ADM('Geoff')('Does the observer want to play?'))
            Echo: << ADM ( "Observer" ) ( "Sorry; I'm just a bot." )
            >>> p.handle_ADM(ADM('Geoff')('Are you sure about that?'))
            Echo: << ADM ( "Observer" ) ( "Yes, I'm sure." )
            >>> p.handle_ADM(ADM('DanM')('Do any other observers care to jump in?'))
        '''#'''
        import re
        sorry = "Sorry; I'm just a bot."
        s = message.fold()[2][0]
        if self.admin_state == 0:
            if '?' in s and s.find('bserver') > 0:
                self.admin_state = 1
                self.send_admin(sorry)
        elif self.admin_state == 1:
            if s == sorry: self.admin_state = 2
        elif self.admin_state == 2:
            self.admin_state = 3
            if '?' in s:
                result = re.match('[Aa]re you (sure|positive|really a bot|for real)', s)
                if result: self.send_admin("Yes, I'm %s." % result.group(1))
                elif re.match('[Rr]eally', s): self.send_admin("Yup.")
                elif re.match('[Ww]ho', s): self.send_admin("Eric.")
            elif re.match('[Nn]ot .*again'): self.send_admin("Fine, I'll shut up now.")

class Sizes(AutoObserver):
    ''' An observer that simply prints power sizes.'''
    def handle_SCO(self, message):
        self.log_debug(1, 'Supply Centres: ' + '; '.join([
            '%s, %d' % (dist[0], len(dist) - 1)
            for dist in message.fold()[1:]
        ]))

class Clock(AutoObserver):
    ''' An observer that simply asks for the time.
        Useful to get timestamps into the server's log.
    '''#'''
    name = 'Time Keeper'
    def handle_HLO(self, message):
        self.__super.handle_HLO(self, message)
        max_time = max(self.opts.BTL, self.opts.MTL, self.opts.RTL)
        if max_time > 0:
            for seconds in range(5, max_time, 5): self.send(TME(seconds))
        else: self.close()
    def handle_TME(self, message):
        import time
        seconds = message[2].value()
        self.log_debug(1, '%d seconds left at %s', seconds, time.ctime())


class Ladder(AutoObserver):
    ''' An observer to implement a ratings ladder.'''
    
    name = 'Ladder'
    score_file = 'log/stats/ladder_scores'
    
    def __init__(self, *args):
        self.__super.__init__(*args)
        self.winners = []
    
    def handle_DRW(self, message):
        if len(message) > 3: self.winners = message[2:-1]
    def handle_SLO(self, message):
        self.winners = [message[2]]
    def handle_SMR(self, message):
        player_list = message.fold()[2:]
        num_players = len(player_list)
        num_winners = 0
        participants = {}
        if self.winners:
            def won(power, centers, winners=self.winners):
                return power in winners
        else:
            def won(power, centers):
                return centers > 0
        
        # Information-gathering loop
        for player in player_list:
            power,name,version,centers = player[:4]
            stats = participants.setdefault((name[0], version[0]), [0,0])
            if won(power, centers):
                num_winners += 1
                stats[0] += 1
            else: stats[1] += 1
        
        win_factor = num_players / num_winners
        scores = self.read_scores()
        self.log_debug(9, 'Initial scores:', scores)
        report = ['Ladder scores have been updated as follows:']
        
        # Scoring loop
        for key, stat_list in participants.iteritems():
            diff = (win_factor * stat_list[0]) - (stat_list[0] + stat_list[1])
            if scores.has_key(key): scores[key] += diff
            else: scores[key] = diff
            if diff < 0: gain = 'loses'
            else: gain = 'gains'
            change = abs(diff)
            report.append('%s (%s) %s %g point%s, for a total of %g.'
                % (key[0], key[1], gain, change, s(change), scores[key]))
        
        # Report results
        self.store_scores(scores)
        for line in report: self.send_admin(line); self.log_debug(9, line)
        if self.quit: self.close()
    
    def read_scores(self):
        try:
            result = load(open(self.score_file))
            if not isinstance(result, dict): result = {}
        except: result = {}
        return result
    def store_scores(self, scores):
        try: dump(scores, open(self.score_file, 'w'))
        except IOError: pass

class Echo(AutoObserver):
    ''' An observer that prints any received message to standard output.'''
    def send(self, message):
        self.log_debug(1, '<< ' + str(message))
        self.__super.send(message)
    
    def handle_message(self, message):
        self.log_debug(1, '>> ' + str(message))
        self.__super.handle_message(message)


if __name__ == "__main__":
    from main import run_player
    run_player(HoldBot, True, True)
