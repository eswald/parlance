r'''Holland - A bot based on JH Holland's classifier systems
    Copyright (C) 2009  Eric Wald
    
    This software may be reused for non-commercial purposes without charge,
    and without notifying the authors.  Use of any part of this software for
    commercial purposes without permission from the authors is prohibited.
'''#'''

from __future__ import division

from bisect import bisect
from math import exp, log
from random import random, uniform, randrange
from struct import pack, unpack

from parlance.fallbacks import defaultdict
from parlance.gameboard import Turn
from parlance.player import Player

def weighted_choice(choices):
    r'''Chooses among values with different desired probabilities.
        Expects `choices` to be a mapping of key => weight.
    '''#"""#'''
    keys = list(choices)
    if not keys:
        raise ValueError("No values to choose from: " + repr(keys))
    
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
    class Adaptive(object):
        valid_order_bonus = 50      # Issuing an acceptable order
        cooperation_bonus = 60      # Divided among participating orders
        takeover_bonus = 500        # Taking a new center
        destruction_bonus = 300     # Leaving an opposing unit without retreat
        winner_bonus = 27720        # Winning the game; deducted for draws
    
    def process_map(self):
        # Todo: Collect the rules from more permanent storage.
        self.agent = Agent([])
        self.values = Adaptive()
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

class Collective(object):
    class Adaptive(object):
        # See the XCS paper for details: Butz and Wilson, 2001
        # http://citeseer.ist.psu.edu/old/700101.html
        N = population_size = 1000
        B = learning_rate = .1
        a = accuracy_slope = .1
        e0 = error_minimum = 10
        v = power_parameter = -5
        g = discount_factor = .8
        OGA = ga_threshold = 40
        X = crossover_prob = .75
        u = mutation_prob = .01
        Odel = experience_threshold = 20
        d = fitness_threshold = .1
        Osub = subsumption_threshold = 50
        P = mask_probability = .3
        p1 = initial_prediction = 1
        e1 = initial_error = .1
        F1 = initial_fitness = .1
        pexplr = exploration_probability = .25
        Omna = coverage_threshold = 10
        
        # Reduced learning rate for the environmental error
        Be = variance_learning_rate = .05
        
        # Subsumption is probably not useful here.
        doGASubsumption = False
        doActionSetSubsumption = False
    
    # Todo: Consider weak refs for this
    singletons = {}
    
    def __new__(cls, table):
        try:
            result = cls.singletons[table]
        except KeyError:
            result = object.__new__(cls)
            cls.singletons[table] = result
            result.init(table)
        return result
    
    def init(self, table):
        # Not __init__, because that gets run too often.
        self.values = self.Adaptive()
        self.rules = self.retrieve(table)
        self.timestamp = 0
    
    def retrieve(self, table):
        try:
            from pymongo import Connection
        except ImportError:
            rules = []
        else:
            self.table = Connection().parang[table]
            rules = [Classifier(row) for row in self.table.find()]
        return rules
    
    def save(self, rule):
        # Called whenever a classifier is created or changed.
        if self.table:
            if rule.n > 0:
                uid = self.table.save(rule.values())
                rule._id = uid
            elif rule._id:
                self.table.remove(rule._id)
    
    def generate(self, msg):
        self.timestamp += 1
        results = defaultdict(list)
        
        for rule in self.rules:
            output = rule.matches(msg)
            if output is not None:
                results[output].append(rule)
        
        while sum(r.n for s in results for r in results[s]) < self.values.Omna:
            rule = self.coverage(msg, results)
            output = rule.matches(msg)
            results[output].append(rule)
            self.delete()
        
        actions = dict((key, sum(r.p * r.F for r in results[key]) /
                sum(r.F for r in results[key]))
            for key in results
            if results[key])
        action = weighted_choice(actions)
        action_set = results[action]
        
        brigade = self.values.g * max(actions.values())
        return action, action_set, brigade
    
    def coverage(self, msg, actions):
        r"Creates a new classifier to fit the under-represented message."
        
        # Ignore only P% of the pattern bits.
        mask = 0
        for n in range(Classifier.bits):
            if random() > self.values.P:
                mask |= 1 << n
        
        while True:
            # Generate an action not in the match set.
            # This also guarantees that the new classifier is unique.
            action = randrange(1 << Classifier.bits)
            if action not in actions:
                break
        
        values = {
            "pattern": msg,
            "pattern_mask": mask,
            "output": action,
            "output_mask": 0,
            "prediction": self.values.p1,
            "error": self.values.e1,
            "fitness": self.values.F1,
            "experience": 0,
            "timestamp": self.timestamp,
            "setsize": 1,
            "numerosity": 1,
        }
        
        rule = Classifier(values)
        self.rules.append(rule)
        self.save(rule)
        return rule
    
    def update(self, action_set, bonus, msg):
        # Update the action set
        set_size = sum(rule.n for rule in action_set)
        if not set_size:
            # All classifiers have been deleted.
            # Continuing would cause division by zero errors.
            return
        
        # Factor out the error due to environmental changes
        ubar = min(bonus - rule.p for rule in action_set)
        
        accuracy = 0
        for rule in action_set:
            rule.exp += 1
            factor = max(1. / rule.exp, self.values.B)
            
            # Reordering these updates may help for more complex problems.
            rule.u += (ubar - rule.u) * self.values.Be
            diff = bonus - rule.p
            rule.p += diff * factor
            err = abs(diff) - rule.u
            if err < 0: err = self.values.e0
            rule.e += (err - rule.e) * factor
            
            rule.s += (set_size - rule.s) * factor
            
            if rule.e < self.values.e0:
                rule.k = 1
            else:
                rule.k = self.values.a * (rule.e / self.values.e0) ** self.values.v
            accuracy += rule.k * rule.n
        
        # Update the fitness separately, using the total accuracy.
        for rule in action_set:
            rule.F += (rule.k * rule.n / accuracy - rule.F) * self.values.B
        
        for rule in action_set:
            self.save(rule)
        
        # Run the genetic algorithm every so often
        avetime = sum(r.ts * r.n for r in action_set) / set_size
        if self.timestamp - avetime > self.values.OGA:
            self.genetic(action_set, msg)
    
    def genetic(self, action_set, msg):
        # Set timestamps for future use
        for rule in action_set:
            rule.ts = self.timestamp
        
        # Choose two, based on their fitness values
        fitness = dict((rule, rule.F) for rule in action_set)
        first = weighted_choice(fitness).copy()
        second = weighted_choice(fitness).copy()
        
        if random() < self.values.X:
            self.crossover(first, second)
        
        self.mutate(first, msg)
        self.mutate(second, msg)
        self.insert(first)
        self.insert(second)
        self.delete()
    
    def crossover(self, first, second):
        x = randrange(Classifier.bits)
        y = randrange(Classifier.bits)
        if x > y:
            x, y = y, x
        
        mask = 0
        for n in range(x, y + 1):
            mask |= 1 << n
        
        fp, fpm, fo, fom = first.unpack()
        sp, spm, so, som = second.unpack()
        
        # Swap the pattern, using the bitwise trick
        fp ^= sp & mask
        sp ^= fp & mask
        fp ^= sp & mask
        
        # Swap the pattern mask
        fpm ^= spm & mask
        spm ^= fpm & mask
        fpm ^= spm & mask
        
        first.pack(fp, fpm, fo, fom)
        second.pack(sp, spm, so, som)
        
        # Average out the performance measurements
        first.p = second.p = (first.p + second.p) / 2
        first.e = second.e = (first.e + second.e) / 2
        first.F = second.F = (first.F + second.F) / 2
    
    def mutate(self, rule, msg):
        prob = self.values.u
        pattern, pattern_mask, output, output_mask = rule.unpack()
        
        for n in range(Classifier.bits):
            bit = 1 << n
            if random() < prob:
                # Mutate only within the matching niche
                pattern_mask ^= bit
                if msg & bit:
                    pattern |= bit
                else:
                    pattern &= ~bit
            if random() < prob:
                output ^= bit
            if random() < prob:
                output_mask ^= bit
        
        # Save the new values
        rule.pack(pattern, pattern_mask, output, output_mask)
        
        # Temporarily decrease fitness
        rule.F *= 0.1
    
    def insert(self, rule):
        for r in self.rules:
            if r.chromosome == rule.chromosome:
                r.n += rule.n
                self.save(r)
                break
        else:
            self.rules.append(rule)
            self.save(rule)
    
    def delete(self):
        total = sum(rule.n for rule in self.rules)
        excess = total - self.values.N
        if excess < 1:
            return []
        
        fitness = sum(rule.F for rule in self.rules) / total
        scores = dict((rule, self.unfitness(rule, fitness))
            for rule in self.rules)
        
        deleted = []
        while excess > 0:
            rule = weighted_choice(scores)
            rule.n -= 1
            if rule.n <= 0:
                self.rules.remove(rule)
                del scores[rule]
                deleted.append(rule)
            self.save(rule)
            excess -= 1
        return deleted
    
    def unfitness(self, rule, average):
        result = rule.n * rule.s
        if rule.exp > self.values.Odel and rule.F < average * self.values.d * rule.n:
            result *= average * rule.n / rule.F
        return result

class Agent(object):
    def __init__(self, table):
        self.parent = Collective(table)
        self.last_action = None
    
    def process(self, msg, bonus=0):
        action, action_set, brigade = self.parent.generate(msg)
        if self.last_action:
            bonus += brigade
            self.parent.update(self.last_action, bonus, self.last_message)
        self.last_action = action_set
        self.last_message = msg
        return action
    
    def reward(self, bonus):
        r"Final reward, for when the next action does not depend on the last."
        self.parent.update(self.last_action, bonus, self.last_message)
        self.last_action = None

class Classifier(object):
    r'''A prediction about the value of an action under certain conditions.
        This is technically a macroclassifier, because it can represent many.
    '''#"""#'''
    
    format = "=LLLL"
    bits = 32
    
    def __init__(self, values):
        chromosome = values.get("chromosome")
        if chromosome:
            self.chromosome = chromosome
            self.set(*self.unpack())
        else:
            pattern = values["pattern"]
            pattern_mask = values["pattern_mask"]
            output = values["output"]
            output_mask = values["output_mask"]
            self.pack(pattern, pattern_mask, output, output_mask)
        
        # These names come from Butz and Wilson, 2001
        self.p = values["prediction"]
        self.e = values["error"]
        self.F = values["fitness"]
        self.exp = values["experience"]
        self.ts = values["timestamp"]
        self.s = values["setsize"]
        self.n = values["numerosity"]
        
        # For better handling of stochastic environments
        # Lanzi and Colombetti, 1999(c)
        self.u = values.get("variance", 0)
        
        # For saving in MongoDB
        self._id = values.get("_id")
    
    def unpack(self):
        return unpack(self.format, self.chromosome)
    def pack(self, pattern, pattern_mask, output, output_mask):
        self.chromosome = pack(self.format,
            pattern, pattern_mask, output, output_mask)
        self.set(pattern, pattern_mask, output, output_mask)
    def set(self, pattern, pattern_mask, output, output_mask):
        # Save not the real values, but the ones we need to use.
        self.pattern_mask = pattern_mask
        self.pattern = pattern & pattern_mask
        self.output_mask = output_mask
        self.output = output & ~output_mask
    
    def matches(self, msg):
        if (msg & self.pattern_mask) == self.pattern:
            return self.output | (msg & self.output_mask)
        else:
            return None
    
    def values(self):
        try:
            from pymongo.binary import Binary
        except ImportError:
            Binary = str
        
        values = {
            "chromosome": Binary(self.chromosome),
            "prediction": self.p,
            "error": self.e,
            "fitness": self.F,
            "experience": self.exp,
            "timestamp": self.ts,
            "setsize": self.s,
            "numerosity": self.n,
            "variance": self.u,
        }
        
        if self._id is not None:
            values["_id"] = self._id
        return values
    
    def copy(self):
        vals = self.values()
        vals["numerosity"] = 1
        vals["experience"] = 0
        return Classifier(vals)

