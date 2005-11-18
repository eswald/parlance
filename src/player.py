import config
from cPickle   import dump, load
from random    import randrange, shuffle
from sets      import Set
from functions import autosuper, Verbose_Object
from orders    import *

class client_options(config.option_class):
    ''' Options for client behavior, including:
        - response      What to do when the Server sends something we don't understand
        - validate      Whether to check the syntax of incoming messages
        - confirm       Whether to send admin messages reporting order submission
    '''#'''
    section = 'clients'
    def __init__(self, player_class):
        self.response    = self.getstring('invalid message response', 'ignore').lower()
        self.validate    = self.getboolean('validate incoming messages', True)
        self.confirm     = self.getboolean('confirm order submission', False)
        functions = {
            int:  self.getint,
            str:  self.getstring,
            bool: self.getboolean,
            list: self.getlist,
        }
        for name,otype,text,default in player_class.options:
            setattr(self, name, functions[otype](text, default))

class Player(Verbose_Object):
    ''' Generic Diplomacy player.
        This class contains methods useful for all players,
        but is designed to be subclassed.
        Handle messages from the server by defining a handle_XXX method,
        where XXX is the name of the first token in the message.
        This class defines handlers for the following:
            MAP, MDF, HLO, DRW, SLO, OFF, SVE, LOD, and FRM
        Most of them do everything you will need,
        in combination with instance variables.
    '''
    # Magic variables:
    name = None        # Set this to a string for all subclasses.
    version = None     # Set this to a string to allow registration as a player.
    description = None # Set this to a string to allow use as a bot.
    options = ()       # Set of tuples: (name, type, config text, default)
    
    def __init__(self, send_method, representation, **kwargs):
        ''' Initializes the instance variables.'''
        self.client_opts = client_options(self.__class__)
        self.send_out  = send_method      # A function that accepts messages
        self.rep       = representation   # The representation message
        self.closed    = False # Whether the connection has ended, or should end
        self.in_game   = False # Whether the game is currently in progress
        self.submitted = False # Whether any orders have been submitted this turn
        self.map       = None  # The game board
        self.saved     = {}    # Positions saved from a SVE message
        self.press_tokens = [] # Tokens to be sent in a TRY message
        self.bcc_list  = {}    # Automatic forwarding setup: sent messages
        self.fwd_list  = {}    # Automatic forwarding setup: received messages
        self.pressed   = {}    # A list of messages received and sent
        self.opts      = None  # The variant options for the current game
        self.use_map   = True  # Whether to initialize a Map; saves time for simple observers
        self.quit      = True  # Whether to close immediately when a game ends
        self.draws     = []    # A list of acceptable draws
        
        # Usefully sent through keyword arguments
        power = kwargs.get('power')     # The power being played, or None
        pcode = kwargs.get('passcode')  # The passcode from the HLO message
        if power:
            try: self.power = Token(power, rep=representation)
            except ValueError:
                self.log_debug(1, 'Invalid power "%r"', power)
                self.power = None
            try: self.pcode = int(pcode)
            except ValueError:
                self.log_debug(1, 'Invalid passcode "%r"', pcode)
                self.pcode = None
            self.log_debug(7, 'Using power=%r, passcode=%r', self.power, self.pcode)
        else: self.power = self.pcode = None
        
        # A list of variables to remember across SVE/LOD
        self.remember  = ['map', 'in_game', 'power', 'pcode', 'bcc_list', 'fwd_list', 'pressed', 'draws']
        
        # Register with the server
        self.send_identity(kwargs.get('game_id'))
    def prefix(self):
        if self.power: return '%s (%s)' % (self.__class__.__name__, self.power)
        else: return self.__class__.__name__
    prefix = property(fget=prefix)
    
    def close(self):
        ''' Informs the player that the connection has closed.'''
        self.in_game = False
        self.closed = True
    
    def send(self, message):
        if not self.closed: self.send_out(message)
    def send_list(self, message_list):
        'Sends a list of Messages to the server.'
        for msg in message_list: self.send(msg)
    def accept(self, message): self.send(YES(message))
    def reject(self, message): self.send(REJ(message))
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
    def phase(self): return self.map.current_turn.phase()
    
    def send_identity(self, game_id=None):
        ''' Registers the player with the server.
            Should send OBS, NME, or IAM.
            Unless overridden, sends IAM with a valid power and passcode,
            NME with a valid name and version, OBS otherwise.
            If game_id is not None, sends a SEL (game_id) message first.
        '''#'''
        if game_id is not None: self.send(SEL(game_id))
        if self.power and self.pcode is not None:
            self.send(IAM(self.power, self.pcode))
        elif self.name and self.version:
            self.send(NME(self.name, self.version))
        else: self.send(OBS())
    
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
            if self.opts: level = self.opts.LVL
            else:         level = -1
            reply = message.validate(self.power, level, True)
        else: reply = None
        if reply:
            self.handle_invalid(message, reply=reply)
        else:
            # Note that try: / except AttributeError: doesn't work below,
            # because the method calls might produce AttributeErrors.
            method_name = 'handle_'+message[0].text
            
            # Special handling for common prefixes
            if message[0] in (YES, REJ, NOT):
                method_name += '_' + message[2].text
            self.log_debug(15, 'Searching for %s() handlers', method_name)
            
            # Call map handlers first
            if self.map and hasattr(self.map, method_name):
                try: getattr(self.map, method_name)(message)
                except Exception, e: self.handle_invalid(message, error=e)
            
            # Then call client handlers
            if hasattr(self, method_name):
                try: getattr(self, method_name)(message)
                except Exception, e: self.handle_invalid(message, error=e)
        self.log_debug(12, 'Finished %s message', message[0])
    
    def handle_invalid(self, message, error=None, reply=None):
        response = self.client_opts.response
        if response in ('print', 'warn', 'carp', 'croak'):
            if error: self.log_debug(1, 'Error processing command: ' + str(message))
            else:     self.log_debug(1, 'Invalid server command: '   + str(message))
        if response in ('huh', 'complain', 'carp', 'croak'):
            self.send(reply or HUH([ERR, message]))
        if response in ('die', 'close', 'carp', 'croak'): self.close()
        if error and response not in ('print', 'close', 'huh', 'carp', 'ignore'): raise
    
    def handle_MAP(self, message):
        ''' Handles the MAP command, creating a new map if possible.
            Sends MDF for unknown maps, YES for valid.
        '''#'''
        if self.use_map:
            from gameboard import Map
            self.map = Map(message.fold()[1][0], self.rep)
            if self.map.valid: self.accept(message)
            else:              self.send(MDF())
        else: self.accept(message)
    def handle_MDF(self, message):
        ''' Replies to the MDF command.
            The map should have loaded itself, but might not be valid.
        '''#'''
        if self.map:
            if self.map.valid: self.accept(MAP(self.map.name))
            else:              self.reject(MAP(self.map.name))
        else: raise ValueError, 'MDF before MAP'
    
    def handle_HLO(self, message):
        self.pcode = message[5]
        power = message[2]
        if power.is_power(): self.power = self.map.powers[power]
        self.in_game = True
        self.opts = config.game_options(message)
        if self.opts.TRN > 1: self.quit = False
    def handle_PNG(self, message): self.accept(message)
    
    def missing_orders(self):
        return self.orders.missing_orders(self.phase(), self.power)
    def handle_MIS(self, message):
        self.log_debug(7, 'Missing orders for %s: %s; %s',
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
    
    def handle_NOW(self, message):
        ''' Requests draws, and calls generate_orders() in a separate thread.'''
        if self.in_game and self.power:
            from threading import Thread
            #self.send(MIS())
            self.submitted = False
            self.orders = OrderSet(self.power)
            if self.draws: self.request_draws()
            if self.missing_orders():
                Thread(target=self.generate_orders).start()
    def request_draws(self):
        current = Set(self.map.current_powers())
        for power_set in self.draws:
            if power_set == current: self.send(DRW())
            elif self.opts.PDA and power_set <= current:
                self.send(DRW(power_set))
    def generate_orders(self):
        ''' Create and send orders.
            Warning: Take care to make this function thread-safe;
            in particular, it must not use global or class variables
            that it sets.
        '''#'''
        raise NotImplementedError
    
    def wait_for_map(self):
        from time import sleep
        while not self.map:
            if self.closed: return
            else: sleep(1)
        if self.map.valid:
            self.send(HLO())
            self.send(SCO())
            self.send(NOW())
    def handle_YES_IAM(self, message):
        if not self.map:
            self.send(MAP())
            from threading import Thread
            Thread(target=self.wait_for_map).start()
        elif not self.power:
            self.send(HLO())
            self.send(SCO())
            self.send(NOW())
    def handle_REJ_IAM(self, message): self.close()
    def handle_REJ_NME(self, message): self.close()
    def handle_OFF(self, message): self.close()
    def game_over(self, message):
        if self.quit: self.close()
        else: self.in_game = False
    handle_DRW = game_over
    handle_SLO = game_over
    handle_SMR = game_over
    
    def handle_SVE(self, message):
        ''' Attempts to save everything named by self.remember.'''
        from copy      import deepcopy
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
            if self.power: self.send(IAM(self.power, self.pcode))
            else: self.accept(message)
        else: self.reject(message)
    
    def handle_FRM(self, message):
        ''' Default press handler.
            Attempts to dispatch it to a handle_press_XXX message.
            Also forwards it, if automatic forwarding has been requested.
            Implements the suggested response for unhandled messages.
        '''#'''
        folded = message.fold()
        mid    = folded[1]
        recips = folded[2]
        press  = folded[3]
        sender = mid[0]

        # Save it for future reference
        self.pressed.setdefault(sender,{}).setdefault(mid[1],[]).append(message)
        
        # Forward it if requested, but avoid loops
        if self.fwd_list.has_key(sender) and press[0] != FRM:
            self.send_press(self.fwd_list[sender], FRM(sender, recips, press), [mid])
        
        # Pass it off to a handler method
        if press[0] in self.press_tokens:
            if len(press) > 4: refs = folded[5:]
            else:              refs = None
            try:
                method_name = 'handle_press_'+press[0].text
                getattr(self, method_name)(mid, message, refs)
                return
            except AttributeError: pass

        # If that fails, reply with HUH/TRY
        self.send_press(sender, HUH([ERR, press]), [mid])
        self.send_press(sender, TRY(self.press_tokens))
    
    def send_press(self, recips, press, refs = None):
        if not (self.in_game and self.power): return
        
        # Standardize inputs
        if not isinstance(recips, list): recips = [recips]
        
        # Forward, if requested
        mid = self.select_id()
        for recipient in recips:
            if self.bcc_list.has_key(recipient) and press[0] != FRM:
                self.send_press(self.bcc_list[recipient],
                    FRM(self.power, recips, press),
                    refs + [(self.power, mid)])

        # Create and store the message
        message = SND(mid, recips, press)
        if refs: message += WRT(*refs)
        self.pressed[self.power].setdefault(mid,[]).append(message)
        
        # Actually send the message
        self.send(message)
    def send_admin(self, text):
        self.send(ADM(self.name or 'Observer', str(text)))
    
    def select_id(self):
        ''' Finds a random unused message id.
            Sequential would be easier, but more revealing.
        '''#'''
        max_int = Token.opts.max_pos_int
        me = self.pressed.setdefault(self.power, {})
        while True:
            num = randrange(-max_int, max_int)
            if not me.has_key(num): break
        return num


class HoldBot(Player):
    ''' A simple bot to hold units in position.'''
    name = 'HoldBot'
    version = 'Python HoldBot v0.2'
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
            self.send(DRW())
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


class Observer(Player):
    ''' Just watches the game, declining invitations to join.'''
    def __init__(self, *args):
        self.__super.__init__(*args)
        self.use_map = False
        self.admin_state = 0
    def handle_ADM(self, message):
        ''' Try to politely decline invitations,
            without producing too many false positives.
            
            >>> p = Echo(lambda x: None, {})
            << OBS
            >>> p.handle_ADM(ADM('Server',
            ...     'An Observer has connected. Have 5 players and 1 observers. Need 2 to start'))
            >>> p.handle_ADM(ADM('Geoff', 'Does the observer want to play?'))
            << ADM ( "Observer" ) ( "Sorry; I'm just a bot." )
            >>> p.handle_ADM(ADM('Geoff', 'Are you sure about that?'))
            << ADM ( "Observer" ) ( "Yes, I'm sure." )
            >>> p.handle_ADM(ADM('DanM', 'Do any other observers care to jump in?'))
        '''#'''
        import re
        sorry = "Sorry; I'm just a bot."
        s = message.fold()[2][0]
        if self.admin_state == 0:
            if '?' in s and s.find('bserver') > 0:
                self.send_admin(sorry)
                self.admin_state = 1
        elif self.admin_state == 1:
            if s == sorry: self.admin_state = 2
        elif self.admin_state == 2:
            if '?' in s:
                result = re.match('[Aa]re you (sure|positive|really a bot|for real)', s)
                if result: self.send_admin("Yes, I'm %s." % result.group(1))
                elif re.match('[Rr]eally', s): self.send_admin("Yup.")
                elif re.match('[Wh]o', s): self.send_admin("Eric.")
            elif re.match('[Nn]ot .*again'): self.send_admin("Fine, I'll shut up now.")
            self.admin_state = 3

class Sizes(Observer):
    ''' An observer that simply prints power sizes.'''
    def handle_SCO(self, message):
        self.log_debug(1, 'Supply Centres: ' + '; '.join([
            '%s, %d' % (dist[0], len(dist) - 1)
            for dist in message.fold()[1:]
        ]))

class Clock(Observer):
    ''' An observer that simply asks for the time.
        Useful to get timestamps into the server's log.
    '''#'''
    name = 'Time Keeper'
    def handle_HLO(self, message):
        Player.handle_HLO(self, message)
        max_time = max(self.opts.BTL, self.opts.MTL, self.opts.RTL)
        if max_time > 0:
            for seconds in range(5, max_time, 5): self.send(TME(seconds))
        else: self.close()
    def handle_TME(self, message):
        import time
        seconds = message[2].value()
        self.log_debug(1, '%d seconds left at %s', seconds, time.ctime())


class Ladder(Observer):
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
        from functions import s
        from operator  import mul
        
        player_list = message.fold()[2:]
        num_players = len(player_list)
        num_winners = 0
        centers_held = 0
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
            key = (name[0], version[0])
            centers_held += centers
            if won(power, centers): num_winners += 1
            else: centers = -centers
            participants.setdefault(key, []).append(centers)
        
        num_losers = (num_players - num_winners)
        loss_factor = reduce(mul, range(2, num_players + 1), 1)
        win_factor = (num_losers * loss_factor // num_winners) + centers_held
        scores = self.read_scores()
        self.log_debug(9, 'Initial scores:', scores)
        report = ['Ladder scores have been updated as follows:']
        
        # Scoring loop
        for key, center_list in participants.iteritems():
            diff = 0
            for centers in center_list:
                if centers > 0: diff += win_factor
                else: diff -= loss_factor
                diff -= abs(centers) * num_winners
            if scores.has_key(key): scores[key] += diff
            else: scores[key] = diff
            if diff < 0: gain = 'loses'
            else: gain = 'gains'
            change = abs(diff)
            report.append('%s (%s) %s %d point%s, for a total of %d.'
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

class Echo(Observer):
    ''' An observer that prints any received message to standard output.'''
    def send(self, message):
        self.log_debug(1, '<< ' + str(message))
        self.__super.send(message)
    
    def handle_message(self, message):
        self.log_debug(1, '>> ' + str(message))
        self.__super.handle_message(message)


def _test():
    from main import run_player
    run_player(HoldBot, True, True)
    #import doctest, player
    #return doctest.testmod(player)
if __name__ == "__main__": _test()

# vim: sts=4 sw=4 et tw=75 fo=crql1
