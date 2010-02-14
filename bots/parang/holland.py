r'''Holland - A bot based on JH Holland's classifier systems
    Copyright (C) 2009  Eric Wald
    
    This software may be reused for non-commercial purposes without charge,
    and without notifying the authors.  Use of any part of this software for
    commercial purposes without permission from the authors is prohibited.
'''#'''

from bisect import bisect
from random import uniform
from struct import pack, unpack

from parlance.fallbacks import defaultdict
from parlance.gameboard import Turn
from parlance.player import Player

def weighted_choice(choices):
    r'''Chooses among values with different desired probabilities.
        Expects `choices` to be a mapping of key => weight.
    '''#"""#'''
    keys = list(choices)
    sums = []
    total = 0
    for key in keys:
        total += choices[key]
        sums.append(total)
    
    n = uniform(0, total)
    index = bisect(sums, n)
    return keys[index]

class UnusableMapException(Exception):
    pass

class Holland(Player):
    def process_map(self):
        # Todo: Collect the rules from more permanent storage.
        self.agent = Agent([])
        self.orders = None
        self.memory = dict.fromkeys(self.map.locs, 0)
        self.actions = dict.fromkeys(self.map.locs, [])
        self.routes = {}
        
        try:
            self.process_messages(self.route_messages())
        except UnusableMapException:
            return False
        
        return True
    
    def route_messages(self):
        # Route messages, sent to each location at game start:
        # mmmmmmmm 000010xx aaaaaaaa bbbbbbbb
        # m: Memory (from previous outputs; not generated here)
        # 00 a: Province category
        # 00 b: Number of locations in the province
        # 01 a: Number of outbound-only borders for the province
        # 01 b: Number of outbound-only routes for the location
        # 10 a: Number of inbound-only borders for the province
        # 10 b: Number of inbound-only routes for the location
        # 11 a: Number of two-way borders for the province
        # 11 b: Number of two-way routes for the location
        
        ROUTE_FLAG = 0x080000
        INBOUND_FLAG = 0x020000
        OUTBOUND_FLAG = 0x010000
        
        spaces = self.map.spaces
        for prov in spaces:
            province = spaces[prov]
            category = province.key.category
            pmsg = ROUTE_FLAG | (category << 8) | len(province.locations)
            
            inbound = province.borders_in
            outbound = province.borders_out
            twoway = province.borders_in & province.borders_out
            prov_routes = {
                INBOUND_FLAG: len(inbound - twoway) << 8,
                OUTBOUND_FLAG: len(outbound - twoway) << 8,
                INBOUND_FLAG | OUTBOUND_FLAG: len(twoway) << 8,
            }
            
            if any(num > 0xFF for num in prov_routes.values()):
                # Too large to fit in a single byte.
                raise UnusableMapException
            
            for location in province.locations:
                yield (location.key, pmsg, [])
                
                inbound = set(location.routes_in)
                outbound = set(location.routes_out)
                twoway = inbound & outbound
                self.routes[location.key] = routes = {
                    INBOUND_FLAG: sorted(inbound - twoway),
                    OUTBOUND_FLAG: sorted(outbound - twoway),
                    INBOUND_FLAG | OUTBOUND_FLAG: sorted(twoway),
                }
                
                for key in routes:
                    num = count(routes[key])
                    if num > 0xFF:
                        # Too large to fit in a single byte.
                        raise UnusableMapException
                    
                    msg = ROUTE_FLAG | key | prov_routes[key] | num
                    yield (location.key, msg, [])
    
    def generate_orders(self):
        self.process_messages(self.power_messages())
        while self.missing_orders():
            # Jump-start locations needing orders.
            self.process_messages(self.missing_messages())
        self.submit_set(self.orders)
    
    def process_messages(self, messages):
        queue = list(messages)
        if not queue and self.orders is not None:
            # We don't have a full order set, but nobody's talking.
            # This could happen if we have builds to waive.
            self.orders.complete_set(self.map)
        
        while queue:
            location, msg, precedents = queue.pop(0)
            msg |= self.memory[location]
            result, action_set = self.agent.process(msg)
            self.memory[location] = result & 0xFF000000
            
            # Todo: Interpret the result
    
    def power_messages(self):
        # Power messages, sent to each location every turn:
        # mmmmmmmm 01abcdef ssssssss nnnnnnnn
        # m: Memory (from previous outputs; not generated here)
        # s: Strength (Units or Centers, whichever is greater)
        # n: Power number (0-N)
        # a: Played (whether this is my power)
        # b: Owns this center
        # c: Could build here (home center)
        # d: Has a non-dislodged unit here
        # e: Has a dislodged unit here
        # f: Order required
        POWER_FLAG = 0x400000
        PLAYED_FLAG = 0x200000
        OWNER_FLAG = 0x100000
        HOME_FLAG = 0x080000
        UNIT_FLAG = 0x040000
        DISLODGED_FLAG = 0x020000
        ORDER_FLAG = 0x010000
        
        # Report each power's strength squared over the sum of the squares.
        # This is an approximate measure of how close it is to winning,
        # which should be easier on the agent than a flat number.
        powers = self.map.powers
        strengths = {}
        for nation in powers:
            power = powers[nation]
            strength = max(len(power.units), len(power.centers))
            strengths[nation] = strengths ** 2
        
        # Compute the common factor outside the loop for efficiency.
        # The 0xFF lets it use a full byte, with the top bit being critical.
        factor = 0xFF / sum(strengths.values())
        
        power_messages = {}
        for nation in strengths:
            strength = int(strengths[nation] * factor) << 8
            msg = POWER_FLAG | strength | nation.value()
            if nation == self.power:
                msg |= PLAYED_FLAG
            power_messages[nation] = msg
        
        phase = self.phase()
        if phase == Turn.build_phase:
            moving = False
            surplus = self.power.surplus()
            building = (surplus < 0)
            disbanding = (surplus > 0)
        else:
            moving = (phase == Turn.move_phase)
            building = disbanding = False
        
        spaces = self.map.spaces
        for prov in spaces:
            province = spaces[prov]
            
            # New copy of the messages, for further modification
            msgs = dict(power_messages)
            
            # Todo: Make the neutral Power evaluate to False?
            if province.owner and province.owner != UNO:
                msgs[province.owner] |= OWNER_FLAG
            
            if province.homes:
                for nation in province.homes:
                    msgs[nation] |= HOME_FLAG
                    if building and nation == self.power and not province.units:
                        msgs[nation] |= ORDER_FLAG
            
            for unit in province.units:
                if unit.dislodged:
                    msgs[unit.nation] |= DISLODGED_FLAG
                    if unit.nation == self.power:
                        msgs[unit.nation] |= ORDER_FLAG
                else:
                    msgs[unit.nation] |= UNIT_FLAG
                    if unit.nation == self.power and (moving or disbanding):
                        msgs[unit.nation] |= ORDER_FLAG
            
            messages = msgs.values()
            for location in province.locations:
                for msg in msgs:
                    yield (location.key, msg, [])
    
    def missing_messages(self):
        # Messages to be sent when a location still needs to send orders,
        # but all inter-location communication has stopped.
        # mmmmmmmm 00000000 ssssssss pppppppp
        # m: Memory (from previous outputs; not generated here)
        # s: Surplus (Units - Centers, not counting orders)
        # p: Phase (movement, retreat, or build)
        
        orders = self.orders
        phase = self.map.current_turn.phase()
        surplus = self.power.surplus()
        msg = phase | (surplus << 8)
        
        if phase == Turn.move_phase:
            # Notify any units without an order.
            for unit in self.power.units:
                if not orders.get_order(unit):
                    yield (unit.location.key, msg, [])
        elif phase == Turn.retreat_phase:
            # Notify any dislodged units without an order.
            for unit in self.power.units:
                if unit.dislodged and not orders.get_order(unit):
                    yield (unit.location.key, msg, [])
        elif phase == Turn.build_phase:
            if surplus < 0:
                # Notify any open home centers we might have.
                for prov in self.power.homes:
                    province = self.map.spaces[prov]
                    if not province.units:
                        for location in province.locations:
                            yield (location.key, msg, [])
            elif surplus > 0:
                # Notify any units without an order.
                for unit in self.power.units:
                    if not orders.get_order(unit):
                        yield (unit.location.key, msg, [])
    
    def handle_THX(self, message):
        r'''Rewards rules that submit valid orders.'''
        folded = message.fold()
        result = folded[2][0]
        if result is MBV:
            sent = folded[1]
            for order in self.orders:
                if order.order == sent:
                    self.log.debug("Rewarding rules for valid order: %s", order)
                    self.agent.reward(order.action_set, self.values.valid_order_bonus)
                    
                    # Don't reward the same order twice
                    # (Waives, for example)
                    order.order = None
                    break
        else:
            # Pass it up to the default handler
            Player.handle_THX(self, message)

class Agent(object):
    class Adaptive(object):
        # See the XCS paper for details
        population_size = 200       # N
        learning_rate = .05         # beta
        discount_factor = .001      # gamma
        matchset_stability = 5      # theta
        epsilon = .01               # epsilon-nought
        alpha = .01                 # alpha
        crossover_prob = .05        # chi
        mutation_prob = .001        # mu
        deletion_threshold = .1     # delta
        coverage_minimum = 10       # phi
        mask_prob = .80             # P-#
        initial_prediction = 100    # p-1
        initial_error = .5          # epsilon-1
        initial_fitness = 50        # F-1
        
        valid_order_bonus = 50      # Issuing an acceptable order
        cooperation_bonus = 60      # Divided among participating orders
        takeover_bonus = 500        # Taking a new center
        destruction_bonus = 300     # Leaving an opposing unit without retreat
        winner_bonus = 10000        # Winning the game; deducted for draws
    
    def __init__(self, rules):
        self.values = self.Adaptive()
        self.last_action = []
        self.rules = rules
    
    def process(self, msg):
        results = defaultdict(list)
        
        for rule in self.rules:
            output = rule.matches(msg)
            if output is not None:
                results[output].append(rule)
        
        actions = dict((key, sum(r.strength for r in results[key]))
            for key in results)
        action = weighted_choice(actions)
        action_set = results.pop(action)
        
        return action, action_set
    
    def reward(self, action_set, precedents, bonus):
        pass

class Classifier(object):
    format = "=LLLL"
    
    def __init__(self, chromosome, strength, accuracy, fitness):
        pattern, pattern_mask, output, output_mask = unpack(self.format, chromosome)
        self.pattern = pattern & pattern_mask
        self.pattern_mask = pattern_mask
        self.output = output & ~output_mask
        self.output_mask = output_mask
        self.strength = strength
        self.accuracy = accuracy
        self.fitness = fitness
    
    def matches(self, msg):
        if (msg & self.pattern_mask) == self.pattern:
            return self.output | (msg & self.output_mask)
        else:
            return None
