''' The Judge for the standard map.
    Should work for most maps, but variants may want to re-implement it.
'''#'''
import config
from sets      import Set, ImmutableSet
from functions import any, all, s
from iaq       import DefaultDict
from server    import Judge
from orders    import *
#from orders    import UnitOrder, RemoveOrder, WaiveOrder, \
#                      HoldOrder, DisbandOrder, OrderSet
#from language  import *

def minmax(decision_list):
    ''' Returns the highest maximum and minimum values in the decision list.'''
    min_found = max_found = 0
    for decision in decision_list:
        if decision.min_value > min_found: min_found = decision.min_value
        if decision.max_value > max_found: max_found = decision.max_value
    return min_found, max_found

class datc_options(config.option_class):
    ''' Options from the Diplomacy Adjudicator Test Cases,
        as written by Lucas B. Kruijswijk.
        A few options have additional possibilities, and some are unsupported.
    '''#'''
    section = 'datc'
    def __init__(self):
        self.datc_4a1 = self.getdatc('multi-route convoy disruption',                                          'ab',    'b')
        self.datc_4a2 = self.getdatc('convoy disruption paradoxes',                                            'bdef',  'd')
        self.datc_4a3 = self.getdatc('convoying to adjacent place',                                            'abcdef','f')
        self.datc_4a4 = self.getdatc('support cut on attack on itself via convoy',                             'ab',    'a')
        self.datc_4a5 = self.getdatc('retreat when dislodged by convoy',                                       'ab',    'b')
        self.datc_4a6 = self.getdatc('convoy path specification',                                              'abc',   'b')
        self.datc_4a7 = self.getdatc('avoiding a head to head battle to bounce a unit',                        'ab',    'b')
        self.datc_4b1 = self.getdatc('omitted coast specification in move order when two coasts are possible', 'ab',    'a') # Done!
        self.datc_4b2 = self.getdatc('omitted coast specification in move order when one coast is possible',   'abc',   'c') # Done!
        self.datc_4b3 = self.getdatc('move order to impossible coast',                                         'ab',    'b') # Done!
        self.datc_4b4 = self.getdatc('coast specification in support order',                                   'acde',  'd')
        self.datc_4b5 = self.getdatc('wrong coast of ordered unit',                                            'ab',    'a')
        self.datc_4b6 = self.getdatc('unknown coasts or irrelevant coasts',                                    'ab',    'a')
        self.datc_4b7 = self.getdatc('coast specification in build order',                                     'a',     'a')
        self.datc_4c1 = self.getdatc('missing unit designation',                                               'ab',    'a')
        self.datc_4c2 = self.getdatc('wrong unit designation',                                                 'ab',    'a')
        self.datc_4c3 = self.getdatc('missing unit designation in build order',                                'abc',   'a')
        self.datc_4c4 = self.getdatc('building a fleet in a land area',                                        'ab',    'a')
        self.datc_4c5 = self.getdatc('missing nationality in support order',                                   'ab',    'a')
        self.datc_4c6 = self.getdatc('wrong nationality in support order',                                     'ab',    'a')
        self.datc_4d1 = self.getdatc('multiple order sets with defined order',                                 'b',     'b')
        self.datc_4d2 = self.getdatc('multiple order sets with undefined order',                               'b',     'b')
        self.datc_4d3 = self.getdatc('multiple orders to the same unit',                                       'b',     'b')
        self.datc_4d4 = self.getdatc('too many build orders',                                                  'b',     'b')
        self.datc_4d5 = self.getdatc('multiple build orders for one area',                                     'c',     'c')
        self.datc_4d6 = self.getdatc('too many disband orders',                                                'b',     'b')
        self.datc_4d7 = self.getdatc('waiving builds',                                                         'ab',    'a')
        self.datc_4d8 = self.getdatc('removing a unit in civil disorder',                                      'abcde', 'd')
        self.datc_4d9 = self.getdatc('receiving hold support in civil disorder',                               'ab',    'b')
        self.datc_4e1 = self.getdatc('illegal orders',                                                         'abcd',  'd') # Done!
        self.datc_4e2 = self.getdatc('poorly written orders',                                                  'e',     'e')
        self.datc_4e3 = self.getdatc('implicit orders',                                                        'ab',    'b')
        self.datc_4e4 = self.getdatc('perpetual orders',                                                       'ab',    'b')
        self.datc_4e5 = self.getdatc('proxy orders',                                                           'abc',   'c')
        self.datc_4e6 = self.getdatc('flying dutchman',                                                        'a',     'a')
    def getdatc(self, option, supported, default):
        if self.user_config.has_option(self.section, option):
            value = self.user_config.get(self.section, option)[0]
            if value in supported: return value
        return default
class judge_options(config.option_class):
    ''' Options for the judge, including:
        - draw         Number of total years before a draw is declared
        - static       Number of static years before a draw is declared
        - variant      Name of the variant (not necessarily the map)
    '''#'''
    section = 'judge'
    def __init__(self):
        self.draw       = self.getint('total years before setting draw',  4000)
        self.static     = self.getint('static years before setting draw', 1000)
        self.var_start  = self.getint('years before variable end',        5000)
        self.var_stop   = self.getint('length of variable end',           10)
        self.variation  = self.getfloat('variation of variable end',      1.55)
        self.full_DRW   = self.getboolean('list draw parties in DIAS',    False)
        self.send_SET   = self.getboolean('publish order sets',           False)
        self.send_ORD   = self.getboolean('publish individual orders',    True)

class Standard_Judge(Judge):
    ''' Implementation of the Judge interface, for DAIDE rules.'''
    
    def __init__(self, game_map, game_opts):
        ''' Initializes instance variables.'''
        super(Standard_Judge, self).__init__(game_map, game_opts)
        self.options = options = judge_options()
        self.datc = datc_options()
        self.last_orders = [REJ(ORD)]
        self.next_orders = OrderSet()
        
        # Game-end conditions
        year = self.map.current_turn.year
        self.var_start  = year + options.var_start
        self.var_stop   = self.var_start + options.var_stop
        self.variation  = options.variation
        self.draw_year  = year + options.draw - 1
        self.max_static = options.static
        
        centers = 0
        for prov in self.map.spaces.itervalues():
            if prov.is_supply(): centers += 1
        self.win_condition = (centers // 2) + 1
        self.log_debug(11, 'Setting win_condition to %d.', self.win_condition)
    
    # Requests for information
    def handle_NOW(self, client, message): client.send(self.map.create_NOW())
    def handle_SCO(self, client, message): client.send(self.map.create_SCO())
    def handle_ORD(self, client, message): client.send_list(self.last_orders)
    def handle_HST(self, client, message):
        # Todo: Learn your history!
        client.reject(message)
    
    # Order submission
    def handle_SUB(self, client, message):
        ''' Processes orders submitted by a power.'''
        country = client.country
        if country and self.phase and not self.eliminated(country):
            orders = self.next_orders
            for tlist in message.fold()[1:]:
                power = self.map.powers[country]
                order = UnitOrder(tlist, power, self.map, self.datc)
                note = order.order_note(power, self.phase, orders)
                self.log_debug(14, ' SUB: %s => %s', order, note)
                order.__note = note
                if note == MBV:
                    order.__result = None
                    orders.add(order, country)
                elif self.game_opts.AOA:
                    if order.is_moving() and self.illegal(order):
                        # Make it act like it's holding
                        self.log_debug(13, ' Changing behavior of "%s" (%s) to hold', order, order.__note)
                        order.is_moving = lambda: False
                    order.__result = note
                    orders.add(order, country)
                    note = MBV
                client.send(THX(order, note))
            missing = self.missing_orders(country)
            if missing: client.send(missing)
            else: self.unready.discard(country)
        else: client.reject(message)
    def handle_NOT_SUB(self, client, message):
        ''' Cancels orders submitted by a power.'''
        country = client.country
        if country and self.phase and not self.eliminated(country):
            orders = self.next_orders
            if len(message) > 4:
                # Attempt to remove a specific order
                order = UnitOrder(message[4:-1], country, self.map, self.datc)
                if not orders.remove(order, country):
                    client.reject(message)
                    return
            else: orders.clear(country)
            self.unready.add(country)
            client.accept(message)
        else: client.reject(message)
    def handle_DRW(self, client, message):
        ''' Processes draw requests submitted by a power.'''
        country = client.country
        self.log_debug(11, 'Considering %s from %s', message, country)
        if country and self.phase and not self.eliminated(country):
            winners = self.get_draw_parties(message)
            self.log_debug(11, ' Using %s as the winners', winners)
            if winners:
                self.draws.setdefault(winners, Set()).add(country)
                client.accept(message)
            else: client.reject(message)
        else: client.reject(message)
    def handle_NOT_DRW(self, client, message):
        ''' Cancels draw requests submitted by a power.'''
        country = client.country
        if country and self.phase and not self.eliminated(country):
            try: self.draws[self.get_draw_parties(message[2:-1])].remove(country)
            except KeyError: client.reject(message)
            else: client.accept(message)
        else: client.reject(message)
    def handle_MIS(self, client, message):
        ''' Tells a power which or how many orders have yet to be submitted.'''
        country = client.country
        if country and self.phase and not self.eliminated(country):
            missing = self.missing_orders(country)
            if missing: client.send(missing)
            else: client.reject(message)
        else: client.reject(message)
    
    # Support functions for the above
    def missing_orders(self, country):
        self.log_debug(14, 'Finding missing orders for %s from %s', country, self.next_orders)
        return self.next_orders.missing_orders(self.phase, self.map.powers[country])
    def get_draw_parties(self, message):
        if len(message) == 1: return ImmutableSet(self.map.current_powers())
        elif self.game_opts.PDA:
            winners = message[2:-1]
            if any(winners, self.eliminated):
                self.log_debug(11, 'Somebody among %s has been eliminated', winners)
                return None
            else: return ImmutableSet(winners)
        else:
            self.log_debug(11, 'List of winners not allowed in non-PDA game')
            return None
    def eliminated(self, country):
        ''' Returns the year the power was eliminated,
            or False if it is still in the game.
        '''#'''
        return self.map.powers[country].eliminated
    
    # Turn processing
    def start(self):
        ''' Starts the game, returning SCO and NOW messages.
            >>> from config import game_options
            >>> j = Standard_Judge(standard_map, game_options())
            >>> [msg[0] for msg in j.start()]
            [SCO, NOW]
            >>> hex(j.phase)
            '0x20'
        '''#'''
        self.unready = Set()
        self.static = 0
        self.init_turn()
        return [self.map.opts.start_sco, self.map.opts.start_now]
    def run(self):
        ''' Process orders, whether or not the powers are all ready.
            Returns applicable ORD, NOW, and SCO messages.
            At the end of the game, returns SLO/DRW and SMY messages.
        '''#'''
        msg = self.check_draw()
        if msg:
            results = [msg]
            self.phase = None
        else:
            # Report submitted orders
            turn = self.map.current_turn
            if self.options.send_SET:
                results = self.create_SETs(turn)
            else: results = []
            
            # Execute and report orders
            if self.phase == turn.move_phase:
                orders = self.move_algorithm()
                self.last_orders = orders
            elif self.phase == turn.retreat_phase:
                orders = self.retreat_algorithm()
                self.last_orders.extend(orders)
            elif self.phase == turn.build_phase:
                orders = self.build_algorithm()
                self.last_orders.extend(orders)
            if self.options.send_ORD: results.extend(orders)
            
            # Skip to the next phase that requires action
            while True:
                # TODO: Store orders, SCO, and NOW in self.history
                turn.advance()
                self.phase = turn.phase()
                if self.phase == turn.build_phase:
                    growing = self.map.adjust_ownership()
                    results.append(self.map.create_SCO())
                    msg = self.check_solo(growing)
                if msg:
                    # End the game
                    results.append(msg)
                    results.append(self.map.create_NOW())
                    self.phase = None
                    break
                else:
                    self.init_turn()
                    if self.unready:
                        results.append(self.map.create_NOW())
                        break
        return results
    def create_SETs(self, turn):
        return [SET(nation, turn, *[(order, [order.__note])
                for order in self.next_orders.order_list(nation)])
                for nation in self.map.powers.values()]
    def init_turn(self):
        self.draws = {}
        self.unready.clear()
        self.next_orders.clear()
        self.phase = self.map.current_turn.phase()
        self.unready.update([country for country in self.map.powers
                if self.missing_orders(country)])
    def check_draw(self):
        ''' Checks for the end of the game by agreed draw.
            Note that in a PDA game, if more than one combination
            has everybody's vote, the result is arbitrary.
        '''#'''
        in_game = Set(self.map.current_powers())
        for winners, voters in self.draws.iteritems():
            if voters >= in_game:
                if self.game_opts.PDA: return DRW(winners)
                elif self.options.full_DRW: return DRW(in_game)
                else: return DRW()
        return None
    def check_solo(self, growing):
        ''' Checks for the end of the game by a solo win.
            Also handles draws by ending year.
        '''#'''
        if growing:
            max_seen = 0
            country = None
            for token, power in self.map.powers.iteritems():
                strength = len(power.centers)
                if strength == max_seen: country = None
                elif strength > max_seen: max_seen = strength; country = token
            self.log_debug(11, 'Checking solo, with (%s, %s, %d, %d).',
                    country, growing, max_seen, self.win_condition)
            if country in growing and max_seen >= self.win_condition:
                return SLO(country)
            self.static = 0
        else: self.static += 1
        
        year = self.map.current_turn.year
        self.log_debug(11, 'Now in %s, with %d static year%s.',
                year, self.static, s(self.static))
        if year >= self.draw_year or self.static >= self.max_static:
            return DRW()
        elif self.var_start <= year < self.var_stop:
            self.win_condition -= self.variation
        return None
    
    def build_algorithm(self):
        ''' The main adjudication routine for adjustment phases.
            Returns a list of ORD messages.
        '''#'''
        orders = []
        turn = self.map.current_turn
        for power in self.map.powers.itervalues():
            surplus = power.surplus()
            for order in self.next_orders.order_list(power):
                # Double-check, because previous orders can affect validity.
                result = order.order_note(power, self.phase)
                if result == MBV:
                    if order.order_type == BLD:
                        self.log_debug(11, 'Building %s', order.unit)
                        order.unit.build()
                        surplus += 1
                        result = SUC
                    elif order.order_type == WVE:
                        self.log_debug(11, 'Waiving for %s', power)
                        surplus += 1
                        result = SUC
                    elif order.order_type == REM:
                        self.log_debug(11, 'Removing %s', order.unit)
                        order.unit.die()
                        surplus -= 1
                        result = SUC
                    else:
                        self.log_debug(7, 'Unknown order type %s in build phase', order.order_type)
                        result = FLD
                orders.append(ORD(turn, order, result))
            
            # Handle missing orders
            if surplus > 0:
                units = power.farthest_units(self.map.distance)
                while surplus > 0:
                    unit = units.pop(0)
                    self.log_debug(8, 'Removing %s on behalf of %s', unit, power)
                    orders.append(ORD(turn, RemoveOrder(unit), SUC))
                    unit.die()
                    surplus -= 1
            while surplus < 0:
                self.log_debug(8, 'Waiving on behalf of %s', power)
                orders.append(ORD(turn, WaiveOrder(power), SUC))
                surplus += 1
        return orders
    def retreat_algorithm(self):
        ''' The main adjudication routine for retreat phases.
            Returns a list of ORD messages.
        '''#'''
        orders = []
        removed = []
        destinations = DefaultDict([])
        turn = self.map.current_turn
        for unit in self.map.units:
            if unit.dislodged:
                order = self.unit_order(unit, DisbandOrder)
                if order.order_type == DSB:
                    # Can't delete units while iterating over them
                    removed.append(order.unit)
                    result = SUC
                elif order.order_type == RTO:
                    destinations[order.destination.province.key].append(order)
                    result = None
                else: result = FLD   # Unrecognized order, but correct season
                if result: orders.append(ORD(turn, order, result))
        for unit in removed: unit.die()
        for unit_list in destinations.itervalues():
            if len(unit_list) == 1:
                # Successful retreat
                order = unit_list[0]
                orders.append(ORD(turn, order, SUC))
                order.unit.move_to(order.destination)
            else:
                # Bouncing
                for order in unit_list:
                    orders.append(ORD(turn, order, BNC))
                    order.unit.die()
        return orders
    def move_algorithm(self):
        ''' The main adjudication routine for movement phases.
            Returns a list of ORD messages.
        '''#'''
        # 0) Initialize arrays
        decisions = Decision_Set()
        convoyers = {}
        for province in self.map.spaces.itervalues(): province.entering = []
        
        # 1) Run through the units, collecting orders and checking validity.
        # Each unit gets a Dislodge decision.
        # Each moving unit gets Path, Move, Attack, and Prevent decisions.
        # Each valid supporting unit gets a Support decision.
        # Each province moved into gets a Hold decision.
        for unit in self.map.units:
            order = unit.current_order = self.unit_order(unit, HoldOrder)
            self.log_debug(13, 'Using "%s" for %s', order, unit)
            unit.supports = []
            unit.decisions = {}
            decisions.add(Dislodge_Decision(order))
            if order.is_moving():
                self.add_movement_decisions(order, unit, decisions)
            elif order.__result: pass
            elif order.is_supporting():
                if order.matches(self.next_orders):
                    decisions.add(Support_Decision(order))
                else: order.__result = NSO
            elif order.is_convoying():
                if order.matches(self.next_orders):
                    convoyers[unit.coast.province.key] = order.supported.key
                else: order.__result = NSO
        
        # 2) Clean up order inter-dependencies.
        # Find available routes for convoyed units.
        # Tell supported units about their supports.
        # Each unit in a head-to-head conflict gets a Defend decision.
        for choice in decisions[Decision.PATH]:
            choice.get_routes(convoyers)
        for choice in decisions[Decision.SUPPORT]:
            choice.order.supported.supports.append(choice)
        for choice in decisions[Decision.MOVE]:
            other = self.find_head(choice.order)
            if other:
                decisions.add(Defend_Decision(choice.order))
                for decision in choice.order.unit.decisions.itervalues():
                    decision.head = other
        
        # 3) Initialize the dependencies in each decision.
        decision_list = decisions.sorted()
        for choice in decisions: choice.init_deps()
        
        # 4) Run through the decisions until they are all made.
        while decision_list:
            self.log_debug(11, '%d decisions to make...', len(decision_list))
            for choice in decision_list:
                self.log_debug(14, choice)
                for dep in choice.depends: self.log_debug(15, '- ' + str(dep))
            remaining = [choice for choice in decision_list
                    if not choice.calculate()]
            if len(remaining) == len(decision_list):
                decision_list = self.resolve_paradox(remaining)
            else: decision_list = remaining
        
        # 5) Move units around
        turn = self.map.current_turn
        orders = [ORD(turn, unit.current_order, self.process_results(unit))
                for unit in self.map.units]
        
        # 6) Clean up all of the circular references
        for choice in decisions: del choice.depends
        for unit in self.map.units: del unit.decisions
        
        # 7) Return the ORD messages
        return orders
    
    def find_head(self, order):
        if not order.is_convoyed():
            unit_list = order.unit.coast.province.entering
            for other in order.destination.province.units:
                if other in unit_list and not other.current_order.is_convoyed():
                    return other
        return None
    def add_movement_decisions(self, order, unit, decisions):
        path = Path_Decision(order)
        if order.__result: path.failed = True
        else: decisions.add(path)
        decisions.add(Move_Decision(order))
        decisions.add(Attack_Decision(order))
        decisions.add(Prevent_Decision(order))
        
        into = order.destination.province
        if not into.entering:
            hold = Hold_Decision(into)
            decisions.add(hold)
            into.hold = hold
        into.entering.append(unit)
    def unit_order(self, unit, order_class):
        ''' Returns the last order given by the unit's owner.
            Depends on handle_SUB() to weed out invalid orders.
        '''#'''
        result = self.next_orders.get_order(unit)
        if not result:
            result = order_class(unit)
            result.__result = None
        return result
    def illegal(self, order):
        ''' Called for movement orders, to determine quasi-legality.
            If this returns True, then the unit should act like it's holding;
            False, like it's attempting to move.
        '''#'''
        # Todo: Improve the algorithm for option C;
        # in particular, FAR for convoy paths with missing fleets is okay
        option = self.datc.datc_4e1
        if   option == 'a': return False
        elif option == 'b': return order.__note == NSP
        elif option == 'c': return order.__note in (NSP, FAR, NAS, CST)
        elif option == 'd': return order.__note != MBV
        else: raise NotImplementedError
    def resolve_paradox(self, decisions):
        ''' Resolve the paradox, somehow.
            This may involve circular motion, convoy paradox,
            or stranger things in certain variants.
        '''#'''
        self.log_debug(7, 'Warning: Paradox resolution')
        decision_list = Set(decisions)
        core = self.get_core(decisions)
        convoy = False
        moving_to = Set()
        moving_from = Set()
        self.log_debug(8, 'Choices in paradox core:')
        for choice in core:
            self.log_debug(8, '- %s', choice)
            if choice.type == Decision.MOVE:
                moving_to.add(choice.into.key)
                moving_from.add(choice.order.destination.province.key)
                for unit in choice.into.units:
                    order = unit.current_order
                    if order.is_convoying() and not order.__result:
                        convoy = True
        
        resolved = None
        if convoy: resolved = self.Szykman(core)
        elif moving_to and moving_to == moving_from:
            resolved = self.circular(core)
        if not resolved: resolved = self.fallback(core)
        self.log_debug(8, 'Resolved choices:')
        for choice in resolved:
            self.log_debug(8, '- %s', choice)
            decision_list.discard(choice)
        return decision_list
    def Szykman(self, decisions):
        ''' Applies the Szykman rule for convoy disruption paradoxes:
            Any convoyed units in the paradox are treated as if they held.
        '''#'''
        result = []
        self.log_debug(8, 'Applying Szykman convoy-disruption rule.')
        for choice in decisions:
            if choice.type == Decision.ATTACK and choice.min_value == 0:
                choice.max_value = 0
                move = choice.order.unit.decisions[Decision.MOVE]
                move.failed = True
                prevent = choice.order.unit.decisions[Decision.PREVENT]
                prevent.min_value = prevent.max_value = 0
                result.extend([choice, move, prevent])
        return result
    def circular(self, decisions):
        ''' Resolution for circular movement: All moves succeed.
        '''#'''
        result = []
        self.log_debug(8, 'Applying circular movement rule.')
        for choice in decisions:
            if choice.type == Decision.MOVE:
                choice.passed = True
                result.append(choice)
        return result
    def fallback(self, decisions):
        ''' Fallback method for paradox resolution:
            All moves and supports in the paradox core simply fail.
            Used for paradoxes in unknown variant rule situations.
        '''#'''
        result = []
        self.log_debug(7, 'Applying fallback rule.')
        for choice in decisions:
            if choice.type in (Decision.MOVE, Decision.SUPPORT):
                choice.failed = True
                result.append(choice)
        return result
    def get_core(self, decisions):
        choices = {}
        for choice in decisions:
            choices[choice] = Set([dep for dep in choice.depends
                if dep and not dep.decided()])
            self.log_debug(8, '%s:', choice)
            for dep in choice.depends: self.log_debug(11, '- %s', dep)
        while True:
            additions = False
            for deps in choices.itervalues():
                newdeps = Set()
                for choice in deps:
                    newdeps |= choices[choice]
                if not (newdeps <= deps):
                    deps |= newdeps
                    additions = True
            if not additions: break
        result = decisions
        self.log_debug(8, '%d original decisions', len(decisions))
        for choice,dep_list in choices.iteritems():
            self.log_debug(11, '%s -> depends on %d', choice, len(dep_list))
            if len(dep_list) < len(result): result = dep_list
        return result or decisions
    def process_results(self, unit):
        ''' Returns the result of the unit's order, based on decisions.
            False Path    -> DSR (FAR determined earlier)
            True Dislodge -> RET (Maybe after another result)
            False Support -> CUT (NSO determined earlier)
            False Move    -> BNC (Unless DSR)
            True Move     -> SUC
            True Support  -> SUC
            Convoys and Holds: The document is unclear, so:
            Convoy -> Same as convoyed unit, plus RET if must retreat
            Hold   -> RET if must retreat, SUC otherwise
        '''#'''
        order = unit.current_order
        result = order.__result
        self.log_debug(13, 'Processing %s; %s', order, result)
        if not result:
            for choice in unit.decisions.itervalues():
                self.log_debug(14, '- ' + str(choice))
            if order.is_moving():
                if unit.decisions[Decision.PATH].passed:
                    if unit.decisions[Decision.MOVE].passed:
                        self.log_debug(11, 'Moving %s to %s', unit, order.destination)
                        unit.move_to(order.destination)
                        result = SUC
                    else: result = BNC
                else: result = DSR
            elif order.is_supporting():
                if unit.decisions[Decision.SUPPORT].passed: result = SUC
                else: result = CUT
            elif order.is_convoying():
                self.process_results(order.supported)
                result = order.supported.current_order.__result
            order.__result = result
            self.log_debug(14, 'Final result: %s', result)
        if unit.decisions[Decision.DISLODGE].passed:
            if not unit.dislodged: unit.retreat(self.collect_retreats(unit))
            if result: return (result, RET)
            else: return RET
        else: return result or SUC
    def collect_retreats(self, unit):
        return [coast.maybe_coast for coast in
                [self.map.coasts[key] for key in unit.coast.borders_out]
                if self.valid_retreat(coast, unit.dislodger)]
    def valid_retreat(self, retreat, dislodger):
        if retreat.province == dislodger.coast.province: return False
        for unit in retreat.province.units:
            order = unit.current_order
            if not (order.is_moving() and order.unit.decisions[Decision.MOVE].passed):
                return False
        if retreat.province.entering:
            if retreat.province.hold.max_value > 0: return False
            for unit in retreat.province.entering:
                if unit.current_order.unit.decisions[Decision.PREVENT].max_value > 0:
                    return False
        return True

class Decision_Set(DefaultDict):
    ''' Holds a set of Decisions, separating them by type.
        As a list, they are returned in the following order:
        PATH decisions, ATTACK decisions, SUPPORT decisions, DEFEND decisions,
        PREVENT decisions, HOLD decisions, MOVE decisions, DISLODGE decisions.
        This order attempts to maximize decisions made in the first pass.
        (But it could be better by alternating attack and support...)
    '''#'''
    def __init__(self): super(Decision_Set, self).__init__([])
    def add(self, decision): self[decision.type].append(decision)
    def __iter__(self):
        from itertools import chain
        return chain(*self.itervalues())
    def sorted(self):
        return (self[Decision.PATH] +
                self[Decision.ATTACK] +
                self[Decision.SUPPORT] +
                self[Decision.DEFEND] +
                self[Decision.PREVENT] +
                self[Decision.HOLD] +
                self[Decision.MOVE] +
                self[Decision.DISLODGE])

class Decision(object):
    # Tristate decisions
    MOVE, SUPPORT, DISLODGE, PATH = range(4)
    # Numeric decisions
    ATTACK, HOLD, PREVENT, DEFEND = range(4,8)
    
    type = None
    names = {
        0: 'Move',
        1: 'Support',
        2: 'Dislodge',
        3: 'Path',
        4: 'Attack',
        5: 'Hold',
        6: 'Prevent',
        7: 'Defend',
    }
    
    # We have over a hundred decisions per movement phase;
    # memory management is crucial.
    __slots__ = ('depends', 'head', 'into', 'order')
    
    def __init__(self, order):
        self.depends = []    # Decisions on which this one depends.
        self.head    = None  # Unit moving opposite direction, without convoy.
        self.into    = None  # Province being moved into
        self.order   = order
        
        if self.type != Decision.HOLD:
            order.unit.decisions[self.type] = self
            if order.destination: self.into = order.destination.province
    def __str__(self):
        return '%s decision for %s; %s' % (
            self.names[self.type], self.order.unit, self.state())
    def state(self): raise NotImplementedError

class Tristate_Decision(Decision):
    __slots__ = ('passed', 'failed')
    status = {
        (False, False): 'Undecided',
        (True,  False): 'Passed',
        (False, True):  'Failed',
        (True,  True):  'Confused'
    }
    
    def __init__(self, *args):
        Decision.__init__(self, *args)
        self.passed = False
        self.failed = False
    def decided(self):
        if self.passed and self.failed:
            print 'Error in %s, using' % self
            for choice in self.depends: print '-', choice
        return self.passed or self.failed
    def state(self): return self.status[(self.passed, self.failed)]
class Move_Decision(Tristate_Decision):
    __slots__ = ()
    type = Decision.MOVE
    def init_deps(self):
        add_dep = self.depends.append
        add_dep(self.order.unit.decisions[Decision.ATTACK])
        if self.head: add_dep(self.head.decisions[Decision.DEFEND])
        else:         add_dep(self.into.hold)
        self.depends.extend([unit.decisions[Decision.PREVENT]
                for unit in self.into.entering if unit != self.order.unit])
    def calculate(self):
        ''' Move decision logic
            >>> Vienna = standard_map.coasts[(AMY, VIE, None)]
            >>> Vienna.set_order([MTO, GAL], standard_map)
            >>> Warsaw = standard_map.coasts[(AMY, WAR, None)]
            >>> Warsaw.set_order([MTO, GAL], standard_map)
            >>> Warsaw.decisions = {}; Vienna.decisions = {}
            >>> attack = Attack_Decision(Vienna)
            >>> attack.min_value = attack.max_value = 1
            >>> prevent = Prevent_Decision(Warsaw)
            >>> prevent.min_value = prevent.max_value = 1
            >>> Galicia = standard_map.spaces[GAL]
            >>> Galicia.hold = hold = Hold_Decision(None)
            >>> hold.min_value = hold.max_value = 0
            >>> Galicia.entering = [Warsaw, Vienna]
            >>> choice = Move_Decision(Vienna)
            >>> choice.init_deps()
            >>> for dep in choice.depends: print dep
            ... 
            Attack decision for (AMY VIE); minimum 1, maximum 1
            Hold decision for None; minimum 0, maximum 0
            Prevent decision for (AMY WAR); minimum 1, maximum 1
            >>> choice.calculate()
            True
            >>> print choice
            Move decision for (AMY VIE); Failed
        '''#'''
        attack = self.depends[0]
        min_oppose, max_oppose = minmax(self.depends[1:])
        self.passed = attack.min_value >  max_oppose
        self.failed = attack.max_value <= min_oppose
        if self.passed:
            for unit in self.order.destination.province.units:
                unit.dislodger = self.order.unit
        return self.decided()
class Support_Decision(Tristate_Decision):
    __slots__ = ()
    type = Decision.SUPPORT
    def init_deps(self):
        self.depends = [self.order.unit.decisions[Decision.DISLODGE]] + [
            u.decisions[Decision.ATTACK]
            for u in self.order.unit.coast.province.entering
            if u.coast.province != self.into
        ]
    def calculate(self):
        dislodge = self.depends[0]
        min_oppose, max_oppose = minmax(self.depends[1:])
        self.passed = dislodge.failed and max_oppose == 0
        self.failed = dislodge.passed or  min_oppose >= 1
        return self.decided()
class Dislodge_Decision(Tristate_Decision):
    # Failed: the unit stays; Passed: it must retreat.
    __slots__ = ()
    type = Decision.DISLODGE
    def init_deps(self):
        if self.order.is_moving():
            my_move = self.order.unit.decisions[Decision.MOVE]
        else: my_move = None
        self.depends = [my_move] + [unit.decisions[Decision.MOVE]
            for unit in self.order.unit.coast.province.entering]
    def calculate(self):
        my_move = self.depends[0]
        self.passed = (not my_move or my_move.failed) and any(self.depends[1:], lambda d: d.passed)
        self.failed = (my_move and    my_move.passed) or  all(self.depends[1:], lambda d: d.failed)
        return self.decided()
class Path_Decision(Tristate_Decision):
    __slots__ = ('convoyed', 'routes')
    type = Decision.PATH
    def __init__(self, order):
        Tristate_Decision.__init__(self, order)
        self.convoyed = order.is_convoyed()
        self.routes = []
    def get_routes(self, convoyers):
        if self.convoyed and self.order.unit.can_be_convoyed():
            if self.order.path:
                path_list = [[fleet.coast.province for fleet in self.order.path]]
            else: path_list = self.order.unit.coast.routes.get(self.into.key, None)
            if path_list:
                key = self.order.unit.key
                def available(prov):
                    return convoyers.get(prov.key, None) == key
                self.routes = [
                    sum([[unit.decisions[Decision.DISLODGE] for unit in prov.units] for prov in path], [])
                    for path in path_list if all(path, available)
                ]
    def init_deps(self):
        if self.convoyed: self.depends = Set(sum(self.routes, []))
        else: self.depends = []
    def calculate(self):
        # There should be a way to do it in one pass, but this is easier.
        self.passed = self.calc_path_pass()
        self.failed = self.calc_path_fail()
        return self.decided()
    def calc_path_pass(self):
        # Check for a path with no dislodged units
        if self.convoyed:
            for path in self.routes:
                for choice in path:
                    if not choice.failed: break
                else: return True
            else: return False
        else: return True
    def calc_path_fail(self):
        # Check for a dislodged unit on each path
        if self.convoyed:
            for path in self.routes:
                for choice in path:
                    if choice.passed: break
                else: return False
            else: return True
        else: return False

class Numeric_Decision(Decision):
    ''' A numeric decision, which is decided when the maximum possible value
        is equal to the minimum possible value.
        The minimum never decreases; the maximum never increases.
    '''#'''
    __slots__ = ('min_value', 'max_value')
    def __init__(self, order):
        Decision.__init__(self, order)
        self.min_value = 0
        self.max_value = Token.opts.max_token   # Essentially infinity
    def decided(self):
        if self.max_value < self.min_value:
            print 'Error in %s, using' % self
            for choice in self.depends: print '-', choice
        return self.max_value == self.min_value
    def state(self):
        return 'minimum %d, maximum %d' % (self.min_value, self.max_value)
class Attack_Decision(Numeric_Decision):
    # Strength of the attack
    __slots__ = ()
    type = Decision.ATTACK
    def init_deps(self):
        # Todo: Make this multi-unit safe
        path = self.order.unit.decisions[Decision.PATH]
        move = None
        if not self.head:
            for other in self.into.units:
                if other.current_order.is_moving():
                    move = other.decisions[Decision.MOVE]
        self.depends = [path, move] + self.order.unit.supports
    def calculate(self):
        ''' Attack decision, support code
            >>> Rome = standard_map.coasts[(AMY, ROM, None)]
            >>> Rome.set_order([MTO, VEN], standard_map)
            >>> Venice = standard_map.coasts[(AMY, VEN, None)]
            >>> Venice.set_order([MTO, TRI], standard_map)
            >>> Rome.decisions = {}; Venice.decisions = {}
            >>> Move_Decision(Venice).passed = True
            >>> Path_Decision(Rome).passed = True
            >>> Rome.supports = []
            >>> choice = Attack_Decision(Rome)
            >>> choice.init_deps()
            >>> for dep in choice.depends: print dep
            ... 
            Path decision for (AMY ROM); Passed
            Move decision for (AMY VEN); Passed
            >>> choice.calculate()
            True
            >>> print choice
            Attack decision for (AMY ROM); minimum 1, maximum 1
        '''#'''
        path = self.depends[0]
        move = self.depends[1]
        supports = self.depends[2:]
        def min_test(choice): return choice.passed
        def max_test(choice): return not choice.failed
        self.min_value = self.calc_attack(path, move, supports, min_test)
        self.max_value = self.calc_attack(path, move, supports, max_test)
        #print 'Attack values: "%s" / "%s"' % (self.min_value, self.max_value)
        #print '  from (%s, %s, %s)' % (path, move, supports)
        return self.decided()
    def calc_attack(self, path, move, supports, valid):
        if valid(path):
            valid_supports = filter(valid, supports)
            if self.head or not (move and valid(move)):
                # Todo: Correct this for multiple units
                powers = []
                for other in self.into.units:
                    powers.append(other.nation)
                    if other.nation == self.order.unit.nation: return 0
                else:
                    return 1 + len([choice for choice in valid_supports
                        if choice.order.unit.nation not in powers])
            else: return 1 + len(valid_supports)
        else: return 0
class Hold_Decision(Numeric_Decision):
    # Strength of the defense
    __slots__ = ()
    type = Decision.HOLD
    def __str__(self):
        return '%s decision for %s; %s' % (
            self.names[self.type], self.order, self.state())
    def init_deps(self):
        # Todo: Make this multi-unit safe
        for unit in self.order.units:
            if unit.current_order.is_moving():
                self.depends = [unit.decisions[Decision.MOVE]]
            else: self.depends = [None] + unit.supports
    def calculate(self):
        if self.depends:
            first = self.depends[0]
            if first:
                if first.failed:   self.min_value = self.max_value = 1
                elif first.passed: self.min_value = self.max_value = 0
                else:
                    self.min_value = 0
                    self.max_value = 1
            else:
                self.min_value = self.max_value = 1
                for support in self.depends[1:]:
                    if not support.failed:
                        self.max_value += 1
                        if support.passed:
                            self.min_value += 1
        else: self.max_value = self.min_value = 0
        return self.decided()
class Prevent_Decision(Numeric_Decision):
    __slots__ = ()
    type = Decision.PREVENT
    def init_deps(self):
        path = self.order.unit.decisions[Decision.PATH]
        if self.head: head = self.head.decisions[Decision.MOVE]
        else:         head = None
        self.depends = [path, head] + self.order.unit.supports
    def calculate(self):
        path = self.depends[0]
        head = self.depends[1]
        if path.failed: self.max_value = self.min_value = 0
        else:
            self.max_value = self.min_value = 1
            for support in self.depends[2:]:
                if not support.failed:
                    self.max_value += 1
                    if support.passed: self.min_value += 1
            if head and not head.failed:
                self.min_value = 0
                if head.passed: self.max_value = 0
            elif not path.passed: self.min_value = 0
        return self.decided()
class Defend_Decision(Numeric_Decision):
    __slots__ = ()
    type = Decision.DEFEND
    def init_deps(self): self.depends = self.order.unit.supports
    def calculate(self):
        self.min_value = self.max_value = 1
        for support in self.depends:
            if not support.failed:
                self.max_value += 1
                if support.passed:
                    self.min_value += 1
        return self.decided()


def _test():
    import doctest, judge
    globs = config.extend_globals(judge.__dict__)
    return doctest.testmod(judge, globs=globs)
if __name__ == "__main__": _test()

# vim: sts=4 sw=4 et tw=75 fo=crql1
