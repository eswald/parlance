''' ComboBot - A PyDip bot that evaluates unit combinations
    Copyright (C) 2004-2008  Eric Wald
    
    This software may be reused for non-commercial purposes without charge,
    and without notifying the authors.  Use of any part of this software for
    commercial purposes without permission from the authors is prohibited.
'''#'''

from copy         import copy
from operator     import mul

from parang.dumbbot      import DumbBot
from parlance.functions  import all, any, defaultdict, sublists
from parlance.orders     import *

class ComboBot(DumbBot):
    ''' A bot that considers unit combinations.
        Based on the DumbBot, but with a different movement algorithm.
        ComboBot looks at combinations of related moves;
        for example, a supported attack with another unit trailing.
        (It ignores cycles of its own units, though.
        I do not consider this a loss.)
    '''#'''
    
    def generate_movement_orders(self, values):
        ''' Generate the actual orders for a movement turn.'''
        self.log_debug(10, "Movement orders for %s", self.map.current_turn)
        self.log_debug(11, str(self.map.create_NOW()))
        
        # Find all reasonable order sets
        combos = self.generate_hold_combos() + self.generate_move_combos() + self.generate_convoy_combos()
        self.log_debug(11, 'Considering %d order combos:', len(combos))
        for orders in combos: self.log_debug(11, '    ' + str(orders))
        combo_sets = [(cs.calc_value(values, self.map), cs) for cs in self.combine_combos(combos)]
        combo_sets.sort()
        self.log_debug(11, 'Choosing from among %d order sets:', len(combo_sets))
        for orders in combo_sets: self.log_debug(11, '    %d - %s', *(orders))
        
        # Choose one of the best ones
        best = combo_sets.pop()
        using = best[1]
        while combo_sets:
            second = combo_sets.pop()
            if self.weighted_choice(best[0], second[0]): using = second[1]
            else: break
        self.log_debug(11, 'Selected order set: %s', str(using))
        return using.unit_orders
    
    def generate_hold_combos(self):
        return [OrderCombo(self, [HoldOrder(unit)])
            for unit in self.power.units]
    def generate_move_combos(self):
        adj_provs = defaultdict(list)
        for unit in self.power.units:
            for key in unit.coast.borders_out:
                dest = self.map.coasts[key]
                if not any(other.nation == self.power
                        for other in dest.province.units):
                    adj_provs[key[1]].append(MoveOrder(unit, dest))
        return [OrderCombo(self, combo)
            for value in adj_provs.values()
            for combo in sublists(value)
            if combo]
    
    def generate_convoy_combos(self):
        return sum([self.get_convoys(unit)
            for unit in self.power.units if unit.can_convoy()], [])
    def get_convoys(self, fleet):
        self.log_debug(11, "Considering convoys through %s.", fleet)
        armies = []
        fleets = []
        beaches = []
        coasts = self.map.coasts
        for border in fleet.coast.borders_out:
            prov = coasts[border].province
            key = prov.is_coastal()
            for unit in prov.units:
                if unit.nation == self.power:
                    if unit.can_be_convoyed(): armies.append(unit)
                    elif unit.can_convoy():    fleets.append(unit)
                    key = None
            if key: beaches.append(coasts[key])
        if not armies: return []
        return ([OrderCombo(self,
                [ConvoyingOrder(fleet, army, beach),
                    ConvoyedOrder(army, beach, [fleet])])
                for beach in beaches for army in armies]
            + sum([self.get_multi_convoys(next, [fleet, next], armies)
                for next in fleets], []))
    def get_multi_convoys(self, fleet, path, armies):
        self.log_debug(11, "Considering convoys through %s.",
                '-'.join([unit.coast.province.key.text for unit in path]))
        fleets = []
        beaches = []
        coasts = self.map.coasts
        for border in fleet.coast.borders_out:
            prov = coasts[border].province
            key = prov.is_coastal()
            for unit in prov.units:
                if unit.nation == self.power:
                    if unit.can_convoy(): fleets.append(unit)
                    key = None
            if key: beaches.append(coasts[key])
        return ([OrderCombo(self,
                [ConvoyingOrder(fleet, army, beach),
                    ConvoyedOrder(army, beach, path)])
                for beach in beaches for army in armies]
            + sum([self.get_multi_convoys(next, path + [next], armies)
                for next in fleets if next not in path], []))
    
    def combine_combos(self, combos, base=None):
        ''' Gathers a list of complete order sets from the combos.'''
        if base is None: base = ComboSet(self.power)
        results = []
        roots = list(combos)
        while roots:
            combo = roots.pop()
            compatibility = self.unfilled_orders(base, combo)
            self.log_debug(13, ' Compatibility of %s with %s: %d',
                    combo, base, compatibility)
            if compatibility >= 0:
                new_set = ComboSet(base, combo)
                if compatibility > 0:
                    results.extend(self.combine_combos(roots, new_set))
                    roots.extend(combo.sub_combos)
                else: results.append(new_set)
        return results
    def unfilled_orders(self, base, combo):
        ''' Returns the number of unordered orders left
            if the base ComboSet were combined with the OrderCombo,
            or -1 if the two are incompatible.
            
            No two combos in a set may have an order for the same unit.
            (Currently allowing one HLD order if the other is HLD, SUP, or CVY.)
            No two combos in a set may order units to the same province.
            (But two units within a combo may self-bounce.)
        '''#'''
        result = 0
        for unit in self.power.units:
            base_order = base.unit_orders.get_order(unit)
            combo_order = combo.unit_orders.get_order(unit)
            if base_order:
                if combo_order:
                    if base_order.is_moving() or combo_order.is_moving():
                        # Conflicting orders
                        return -1
                    elif not (base_order.is_holding() or combo_order.is_holding()):
                        return -2
                elif base_order.is_moving() and combo.unit_orders.moving_into(base_order.destination.province):
                    # Both combos are moving to the same province
                    return -3
            elif combo_order:
                if combo_order.is_moving() and base.unit_orders.moving_into(combo_order.destination.province):
                    # Both combos are moving to the same province
                    return -4
            else:
                # Count unordered units
                result += 1
        return result

class OrderCombo(object):
    ''' A combination of coordinated orders.
        Variables:
            - player             The ComboBot
            - unit_orders        OrderSet
            - sub_combos         Combinations that use these orders with others
    '''#'''
    def __init__(self, base, new_orders):
        if isinstance(base, OrderCombo):
            self.player = base.player
            self.unit_orders  = copy(base.unit_orders)
            self.provs_gained = dict(base.provs_gained)
            self.provs_held   = dict(base.provs_held)
            self.provs_lost   = dict(base.provs_lost)
            self.provs_doomed = dict(base.provs_doomed)
        else:
            self.player = base
            self.unit_orders  = OrderSet(base.power)
            self.provs_gained = {}
            self.provs_held   = {}
            self.provs_lost   = {}
            self.provs_doomed = {}
        for order in new_orders: self.unit_orders.add(order)
        #self.recalc_provs(new_orders)
        self.sub_combos = self.get_children(new_orders)
    def __str__(self):
        return "OrderCombo('%s', [%s])" % (
            ", ".join([str(order) for order in self.unit_orders]),
            "; ".join([str(combo) for combo in self.sub_combos]))
    
    def get_children(self, new_orders):
        # Support functions
        def valid(order_list):
            ''' Checks for multiple orders to a single unit, or empty lists.
                Todo: Check for convoy matching.
            '''#'''
            if not order_list: return False
            keys_seen = []
            for order in order_list:
                key = order.unit.key
                if key in keys_seen: return False
                keys_seen.append(key)
            return True
        def attackers(province, friendly=self.player.power.key,
                spaces=self.player.map.spaces):
            ''' Compiles a list of enemy units that can enter the province.'''
            bordering = [spaces[prov].units for prov in province.borders_in]
            return [u for u in sum(bordering, [])
                if u and u.nation != friendly and u.can_move_to(province)]
        def occupied(province, friendly=self.player.power.key):
            ''' Determines whether an enemy is in a space.'''
            return any(unit.nation != friendly for unit in province.units)
        
        # Determine who can still be ordered
        unordered = [u for u in self.player.power.units
            if not self.unit_orders.get_order(u)]
        holding = [order.unit for order in self.unit_orders
            if order.is_holding()]
        if not (unordered or holding): return []
        
        # Collect orders related to the new orders
        sub_orders = []
        enter_provs = []
        for order in new_orders:
            if order.is_moving():
                if (occupied(order.destination.province)
                        or len(attackers(order.destination.province)) > 0):
                    # Try to support the move
                    sub_orders.extend([
                        SupportMoveOrder(u, order.unit, order.destination)
                        for u in unordered + holding
                        if u.can_move_to(order.destination.province)])
                # Try to enter the vacated space
                enter_provs.append(order.unit.coast.province.key)
            else:
                enemies = attackers(order.unit.coast.province)
                if (len(enemies) > 1):
                    # Try to support the stationary unit
                    sub_orders.extend([SupportHoldOrder(u, order.unit)
                        for u in unordered + holding
                        if u.can_move_to(order.unit.coast.province)])
                    # Try to cut support for attacks
                    enter_provs.extend([u.coast.province.key for u in enemies])
                if (order.is_supporting()
                        and order.supported.coast != order.destination
                        and occupied(order.destination.province)):
                    # Try to cut support to the attacked unit
                    enter_provs.extend([u.coast.province.key
                            for u in attackers(order.destination.province)])
                    # Todo: Try to block retreats
        
        # Try to enter indicated provinces
        sub_orders.extend([MoveOrder(u, self.player.map.coasts[key])
                for u in unordered for key in u.coast.borders_out
                if key[1] in enter_provs])
        # Try to convoy to the indicated provinces
        sub_orders.extend(self.convoys_to(enter_provs, unordered, holding))
        
        # Run all possible combinations of the related orders
        return [OrderCombo(self, order_list)
            for order_list in sublists(sub_orders)
            if valid(order_list)]
    def convoys_to(self, prov_list, unordered, holding):
        coasts = self.player.map.coasts
        convoyers = [fleet for fleet in unordered + holding if fleet.can_convoy()]
        all_fleets = {}
        all_armies = {}
        all_beaches = {}
        for fleet in convoyers:
            fleets = all_fleets[fleet.key] = []
            armies = all_armies[fleet.key] = []
            beaches = all_beaches[fleet.key] = []
            for coast in [coasts[key] for key in fleet.coast.borders_out]:
                key = coast.province.is_coastal()
                if key:
                    army = coasts[key]
                    if coast.province in prov_list: beaches.append(army)
                    elif army in unordered: armies.append(army)
                elif coast in convoyers: fleets.append(coast)
        paths = []
        new_paths = [[fleet] for fleet in convoyers]
        while new_paths:
            paths.extend(new_paths)
            new_paths = [route + [fleet]
                for route in new_paths
                for fleet in all_fleets[route[-1].key]
                if fleet not in route]
        return sum([[ConvoyedOrder(army, beach, route)]
            + [ConvoyingOrder(fleet, army, beach) for fleet in route]
            for route in paths
            for army in all_armies[route[0].key]
            for beach in all_beaches[route[-1].key]], [])
        results = []
        for route in paths:
            for army in all_armies[route[0].key]:
                for beach in all_beaches[route[-1].key]:
                    results.append(ConvoyedOrder(army, beach, route))
                    results.extend([ConvoyingOrder(fleet, army, beach)
                            for fleet in route])
        return results

class Memoize:
    ''' Calls the function, caching the results for future use.
        Similar to the one in Peter Norvig's Infrequently Answered Questions,
        at http://www.norvig.com/python-iaq.html
        This implementation keeps the cache in the object.
    '''#'''
    def __init__(self, fn):
        self.fn = fn
    def __call__(self, obj, *args):
        key = (self.fn,) + args
        try:
            if obj.__cache.has_key(key):
                return obj.__cache[key]
        except AttributeError: obj.__cache = {}
        obj.__cache[key] = result = self.fn(obj, *args)
        return result

class ComboSet(object):
    def __init__(self, base, combo=None):
        if combo:
            self.power = base.power
            self.unit_orders = copy(base.unit_orders)
            for order in combo.unit_orders:
                # Update everything except holding orders
                # that would overwrite stationary ones.
                old_order = self.unit_orders.get_order(order.unit)
                if old_order:
                    if not order.is_holding():
                        self.unit_orders.remove(old_order)
                        self.unit_orders.add(order)
                else: self.unit_orders.add(order)
        else:
            self.power = base
            self.unit_orders = OrderSet(base)
    
    def __str__(self):
        return "ComboSet('%s')" % "', '".join([str(order) for order in self.unit_orders])
    
    def calc_value(self, values, board):
        ''' Primitive calculation of the value of the orders.
            The value tends to be underestimated.
            - provs_gained       probability of being there (not there now)
            - provs_held         probability of being there (already there)
            - provs_lost         probability of enemy being there (I'm there or own it)
            - provs_doomed       probability of being destroyed
        '''#'''
        result = 0
        adj_provinces = set()
        for order in self.unit_orders:
            if order:
                unit = order.unit
                # calc held for order.unit
                unit_value = values.destination_value[unit.coast.key]
                result += unit_value * self.stay_prob(unit, False, values.adjacent_units)
                if order.is_moving():
                    # calc gained for order.destination
                    dest_value = values.destination_value[order.destination.key]
                    result += dest_value * self.success_prob(order, False, values.adjacent_units)
                    # calc doomed for order.destination
                    for enemy in order.destination.province.units:
                        dest_worth = dest_value
                        result += dest_worth * self.destroy_prob(enemy, False, values.adjacent_units)
                # calc doomed for order.unit
                unit_worth = unit_value
                result -= unit_worth * self.destroy_prob(order.unit, True, values.adjacent_units)
                # save adjacent provinces for later
                adj_provinces.update([key[1] for key in unit.coast.borders_out])
            else: return 0
        # calc lost for any adjacent province an enemy can move to
        for prov in adj_provinces:
            province = board.spaces[prov]
            prov_value = max([values.destination_value[coast.key] for coast in province.coasts])
            result -= prov_value * self.lost_prob(province, True, values.adjacent_units)
        # calc lost for my SCs that could have an enemy closer than a friend.
        for sc in self.power.centers:
            province = board.spaces[sc]
            sc_value = max([values.destination_value[coast.key] for coast in province.coasts])
            result -= sc_value * self.threat_prob(province, True, values.adjacent_units)
        return result
    
    # Helpers for the *_prob() functions
    def enemies(self, province, nation, adjacent_units):
        return [unit
                for power, unit_list in adjacent_units[province.key].iteritems()
                if power.key not in (nation.key, self.power.key)
                for unit in unit_list
                if unit.coast.province.key != province.key]
    def friends(self, province, adjacent_units):
        return [unit for unit in adjacent_units[province.key][self.power.key]
                if unit.coast.province.key != province.key]
    
    # For the following functions, bias indicates whether to guess aggressively
    # or conservatively, such that foo_prob(x,True) >= foo_prob(x,False).
    def stay_prob(self, unit, bias, adjacent_units):
        ''' How likely a unit is to stay in the province indicated.'''
        result = ((1 - self.dislodge_prob(unit, not bias, adjacent_units))
                * (1 - self.move_prob(unit, not bias, adjacent_units)))
        return result
    def attacked_prob(self, province, nation, force, bias, adjacent_units):
        ''' How likely the province is to be attacked by an enemy of the nation,
            with at least the indicated force.
        '''#'''
        result = 0
        if nation != self.power:
            entering = False
            supports = []
            for unit in self.friends(province, adjacent_units):
                order = self.unit_orders.get_order(unit)
                if order.is_moving():
                    if order.destination.province.key == province.key:
                        entering = True
                elif (order.is_supporting()
                        and order.destination.province.key == province.key
                        and order.supported.coast.province.key != province.key):
                    supports.append(1 - self.success_prob(order, bias, adjacent_units))
            if force == 1: result = entering and 1 or 0
            elif len(supports) >= force - 1:
                # Will my supports work?
                result = 1 - (bias and min or max)([reduce(mul, sl, 1)
                        for sl in sublists(supports) if len(sl) == force - 1])
        
        if bias:
            # Allow mutual enemies to help out
            enemies = self.enemies(province, nation, adjacent_units)
            # Todo: Consider whether they cooperate, ever
            if len(enemies) >= force: result = 1
        return result
    def dislodge_prob(self, unit, bias, adjacent_units):
        ''' How likely the indicated unit is to be dislodged unless it moves.
            Assumes that no enemy units are in the indicated unit's province.
        '''#'''
        enemies = self.enemies(unit.coast.province, unit.nation, adjacent_units)
        # if no more than one enemy unit nearby, 0
        if len(enemies) <= 1: return 0
        # if all nearby enemy units are attacked, 0
        if all(self.attacked_prob(enemy.coast.province, enemy.nation, 1,
                not bias, adjacent_units) == 1 for enemy in enemies):
            return 0
        # Todo: Guess better than this
        strength = 1
        return self.attacked_prob(unit.coast.province, unit.nation,
                strength, bias, adjacent_units)
    def move_prob(self, unit, bias, adjacent_units):
        ''' How likely a unit is to move out of the province indicated.'''
        order = self.unit_orders.get_order(unit)
        if order:
            if order.is_moving(): result = self.success_prob(order, bias, adjacent_units)
            else: result = 0
        else: result = bias and 1 or 0
        return result
    def destroy_prob(self, unit, bias, adjacent_units):
        ''' How likely the given unit is to be destroyed.'''
        return self.dislodge_prob(unit, bias, adjacent_units)
    def threat_prob(self, centre, bias, adjacent_units):
        ''' How likely the given supply center is to have an enemy closer than a friend.'''
        return bias and 1 or 0
    def lost_prob(self, province, bias, adjacent_units):
        ''' How likely the given province is to be taken by an enemy.'''
        return bias and 1 or 0
    def success_prob(self, order, bias, adjacent_units):
        ''' How likely the given order is to succeed.'''
        if order.is_moving():
            # Todo: Consider supports for or against
            probs = [1]
            for unit in order.destination.province.units:
                other_order = self.unit_orders.get_order(unit)
                if other_order:
                    probs.append(1 - self.stay_prob(unit, not bias, adjacent_units))
                else: probs.append(0)
            if order.is_convoyed() and order.path:
                for fleet in order.path:
                    probs.append(1 - self.dislodge_prob(fleet, not bias, adjacent_units))
            result = min(probs)
        elif order.is_supporting():
            result = 1 - self.attacked_prob(order.unit.coast.province,
                    order.unit.nation, 1, not bias, adjacent_units)
        else: result = bias and 1 or 0
        return result
    
    # Cache results of the probability functions
    #stay_prob = Memoize(stay_prob)
    #move_prob = Memoize(move_prob)
    #lost_prob = Memoize(lost_prob)
    #threat_prob = Memoize(threat_prob)
    #success_prob = Memoize(success_prob)
    #destroy_prob = Memoize(destroy_prob)
    #dislodge_prob = Memoize(dislodge_prob)


def run():
    from main import run_player
    run_player(ComboBot)
