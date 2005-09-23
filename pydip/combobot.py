''' ComboBot - A diplomacy bot that evaluates unit combinations
    
    This software may be reused for non-commercial purposes without
    charge, and without notifying the author. Use of any part of this
    software for commercial purposes without permission from the Author
    is prohibited.
'''#'''

from random       import random
from sets         import Set
from dumbbot      import DumbBot
from functions    import sublists
from orders       import *

class ComboBot(DumbBot):
    ''' Based on the DumbBot, but with a different movement algorithm.
        ComboBot looks at combinations of related moves;
        for example, a supported attack with another unit trailing.
        (It ignores cycles of its own units, though.
        I do not consider this a loss.)
    '''#'''
    
    # Items for the NME message
    name    = 'ComboBot'
    version = '0.1'
    description = 'ComboBot - A bot that considers unit combinations'
    static_logfile = 'logs/output_combobot.txt'
    
    def generate_movement_orders(self):
        ''' Generate the actual orders for a movement turn.
        '''#'''
        self.log_debug("Movement orders for %s", self.map.current_turn)
        self.log_debug(str(self.map.create_NOW()))
        
        # Find all reasonable order sets
        combos = self.generate_hold_combos() + self.generate_move_combos() + self.generate_convoy_combos()
        self.log_debug('Considering %d order combos:', len(combos))
        for orders in combos: self.log_debug('    ' + str(orders))
        order_sets = self.combine_combos(combos)
        self.log_debug('Choosing from among %d order sets:', len(order_sets))
        for orders in order_sets: self.log_debug('    ' + str(orders))
        
        # Choose one of the best ones
        order_sets.sort()
        using = best = order_sets.pop()
        while order_sets:
            second = order_sets.pop()
            if self.random_destination(best, second): using = second
            else: break
        self.log_debug('Selected: ' + str(using))
        for order in using.unit_orders.itervalues(): order.apply()
    
    def generate_hold_combos(self):
        return [OrderCombo(self, [HoldOrder(unit)])
            for unit in self.power.units.itervalues()]
    def generate_move_combos(self):
        adj_provs = {}
        for unit in self.power.units.itervalues():
            for key in unit.borders_out:
                dest = self.map.coasts[key]
                other = dest.province.unit
                if not (other and other.nation == self.power):
                    adj_provs.setdefault(key[1], []).append(MoveOrder(unit, dest))
        return [OrderCombo(self, combo)
            for value in adj_provs.values()
            for combo in sublists(value)
            if combo]
    
    def generate_convoy_combos(self):
        return sum([self.get_convoys(unit)
            for unit in self.power.units.itervalues()
            if unit.can_convoy()], [])
    def get_convoys(self, fleet):
        self.log_debug("Considering convoys through %s." % fleet)
        armies = []
        fleets = []
        beaches = []
        coasts = self.map.coasts
        for border in fleet.borders_out:
            prov = coasts[border].province
            key = prov.is_coastal()
            unit = prov.unit
            if unit and unit.nation == self.power:
                if unit.can_be_convoyed(): armies.append(unit)
                elif unit.can_convoy():    fleets.append(unit)
            elif key: beaches.append(coasts[key])
        if not armies: return []
        return ([OrderCombo(self,
                [ConvoyingOrder(fleet, army, beach),
                    ConvoyedOrder(army, beach, [fleet.province])])
                for beach in beaches for army in armies]
            + sum([self.get_multi_convoys(next, [fleet.province, next.province], armies)
                for next in fleets], []))
    def get_multi_convoys(self, fleet, path, armies):
        self.log_debug("Considering convoys through %s." % '-'.join(path))
        fleets = []
        beaches = []
        coasts = self.map.coasts
        for border in fleet.borders_out:
            prov = coasts[border].province
            key = prov.is_coastal()
            unit = prov.unit
            if unit and unit.nation == self.power:
                if unit.can_convoy(): fleets.append(unit)
            elif key: beaches.append(coasts[key])
        return ([OrderCombo(self,
                [ConvoyingOrder(fleet, army, beach),
                    ConvoyedOrder(army, beach, path)])
                for beach in beaches for army in armies]
            + sum([self.get_multi_convoys(next, path + [next.province], armies)
                for next in fleets if next.province not in path], []))
    
    def combine_combos(self, combos, base=None):
        ''' Gathers a list of complete order sets from the combos.
        '''#'''
        if base is None: base = OrderSet(self.power)
        results = []
        roots = list(combos)
        while roots:
            combo = roots.pop()
            compatibility = self.unfilled_orders(base, combo)
            if compatibility >= 0:
                new_set = OrderSet(base, combo)
                if compatibility > 0:
                    results.extend(self.combine_combos(roots, new_set))
                    roots.extend(combo.sub_combos)
                else: results.append(new_set)
        return results
    def unfilled_orders(self, base, combo):
        ''' Returns the number of unordered orders left
            if the base OrderSet were combined with the OrderCombo,
            or -1 if the two are incompatible.
            
            No two combos in a set may have an order for the same unit.
            (Currently allowing one HLD order if the other is HLD, SUP, or CVY.)
            No two combos in a set may order units to the same province.
            (But two units within a combo may self-bounce.)
        '''#'''
        result = 0
        base_into = []
        combo_into = []
        for key, value in base.unit_orders.iteritems():
            order = combo.unit_orders.get(key, None)
            if order is None:
                if value is None:
                    # Count unordered units
                    result += 1
                elif value.is_moving():
                    # Check for self-bounces in different combos
                    prov = value.destination.province.token
                    if prov in combo_into: return -1
                    else: base_into.append(prov)
            elif value is None:
                if order.is_moving():
                    # Check for self-bounces in different combos
                    prov = order.destination.province.token
                    if prov in base_into: return -1
                    else: combo_into.append(prov)
            else:
                # Check for conflicting orders
                if value.is_moving() or order.is_moving(): return -1
                if not (value.is_holding() or order.is_holding()): return -1
        return result

class OrderCombo(object):
    ''' A combination of coordinated orders.
        Variables:
            - player             The ComboBot
            - unit_orders        location_key -> UnitOrder
            - sub_combos         Combinations that use these orders with others
    '''#'''
    def __init__(self, base, new_orders):
        if isinstance(base, OrderCombo):
            self.player = base.player
            self.unit_orders  = dict(base.unit_orders)
            self.provs_gained = dict(base.provs_gained)
            self.provs_held   = dict(base.provs_held)
            self.provs_lost   = dict(base.provs_lost)
            self.provs_doomed = dict(base.provs_doomed)
        else:
            self.player = base
            self.unit_orders  = {}
            self.provs_gained = {}
            self.provs_held   = {}
            self.provs_lost   = {}
            self.provs_doomed = {}
        for order in new_orders:
            self.unit_orders[order.coast.key] = order
        #self.recalc_provs(new_orders)
        self.sub_combos = self.get_children(new_orders)
    def __str__(self):
        return "OrderCombo('%s', [%s])" % (
            ", ".join([str(order) for order in self.unit_orders.itervalues()]),
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
                key = order.coast.key
                if key in keys_seen: return False
                keys_seen.append(key)
            return True
        def attackers(province, friendly=self.player.power.token,
                spaces=self.player.map.spaces):
            ''' Compiles a list of enemy units that can enter the province.
            '''#'''
            bordering = [spaces[prov].unit for prov in province.borders_in]
            return [u for u in bordering if u and u.nation != friendly
                    and u.can_move_to(province)]
        def occupied(province, friendly=self.player.power.token):
            ''' Determines whether an enemy is in a space.
            '''#'''
            unit = province.unit
            return (unit and unit.nation != friendly)
        
        # Determine who can still be ordered
        unordered = [u for u in self.player.power.units.itervalues()
            if not self.unit_orders.has_key(u.key)]
        holding = [order.coast for order in self.unit_orders.itervalues()
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
                        SupportMoveOrder(u, order.coast, order.destination)
                        for u in unordered + holding
                        if u.can_move_to(order.destination.province)])
                # Try to enter the vacated space
                enter_provs.append(order.coast.province.token)
            else:
                enemies = attackers(order.coast.province)
                if (len(enemies) > 1):
                    # Try to support the stationary unit
                    sub_orders.extend([SupportHoldOrder(u, order.coast)
                        for u in unordered + holding
                        if u.can_move_to(order.destination.province)])
                    # Try to cut support for attacks
                    enter_provs.extend([u.province.token for u in enemies])
                if (order.is_supporting()
                        and order.supported != order.destination
                        and occupied(order.destination.province)):
                    # Try to cut support to the attacked unit
                    enter_provs.extend([u.province.token
                            for u in attackers(order.destination.province)])
                    # Todo: Try to block retreats
        
        # Try to enter indicated provinces
        sub_orders.extend([MoveOrder(u, self.player.map.coasts[key])
                for u in unordered for key in u.borders_out
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
            for coast in [coasts[key] for key in fleet.borders_out]:
                key = coast.province.is_coastal()
                if key:
                    army = coasts[key]
                    if coast.province in prov_list: beaches.append(army)
                    elif army in unordered: armies.append(army)
                elif coast in convoyers: fleets.append(coast)
        paths = []
        new_paths = list(convoyers)
        while new_paths:
            paths.extend(new_paths)
            new_paths = [route + [fleet]
                for route in new_paths
                for fleet in all_fleets[route[-1].key]
                if fleet not in route]
        return sum([[ConvoyedOrder(army, beach,
                [fleet.province.token for fleet in route])]
            + [ConvoyingOrder(fleet, army, beach) for fleet in route]
            for route in paths
            for army in all_armies[route[0].key]
            for beach in all_beaches[route[-1].key]], [])
        results = []
        for route in paths:
            for army in all_armies[route[0].key]:
                for beach in all_beaches[route[-1].key]:
                    results.append(ConvoyedOrder(army, beach,
                        [fleet.province.token for fleet in route]))
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
        key = (fn,) + args
        if obj.__cache.has_key(key):
            return obj.__cache[key]
        else:
            obj.__cache[key] = result = self.fn(obj, *args)
            return result

class OrderSet(object):
    def __init__(self, base, combo=None):
        if combo:
            self.power = base.power
            self.unit_orders = dict(base.unit_orders)
            for key, order in combo.unit_orders.iteritems():
                # Update everything except holding orders
                # that would overwrite stationary ones.
                if (not order.is_holding()) or (self.unit_orders[key] is None):
                    self.unit_orders[key] = order
        else:
            self.power = base
            self.unit_orders = dict.fromkeys([u.key for u in base.units.itervalues()])
        self.destination_value = self.calc_value()
    
    def __str__(self):
        return "OrderSet(%s, '%s')" % (self.destination_value,
            "', '".join([str(order) for order in self.unit_orders.itervalues()]))
    def __cmp__(self, other):
        return cmp(self.destination_value, other.destination_value)
    
    def calc_value(self):
        ''' Primitive calculation of the value of the orders.
            The value tends to be underestimated.
            - provs_gained       probability of being there (not there now)
            - provs_held         probability of being there (already there)
            - provs_lost         probability of enemy being there (I'm there or own it)
            - provs_doomed       probability of being destroyed
        '''#'''
        return 1 + random() * .1
        result = 0
        adj_provinces = Set()
        for key, order in self.unit_orders.iteritems():
            if order:
                pass
                # calc held for order.unit
                result += unit.destination_value * self.stay_prob(unit, False)
                if order.is_moving():
                    # calc gained for order.destination
                    result += order.destination * self.success_prob(order, False)
                    # calc doomed for order.destination
                    result += order.destination * self.destroy_prob(order.destination, False)
                # calc doomed for order.unit
                result -= unit.destination_value * self.destroy_prob(order, True)
                # save adjacent provinces for later
                adj_provinces.update(unit.borders_out)
            else: return 0
        # calc lost for any adjacent province an enemy can move to
        for prov in adj_provinces:
            result -= prov.destination_value * self.lost_prob(prov, True)
        # calc lost for my SCs that could have an enemy closer than a friend.
        for sc in self.power.centers:
            result -= sc.destination_value * self.threat_prob(sc, True)
    
    # For the following functions, bias indicates whether to guess aggressively
    # or conservatively, such that foo_prob(x,True) >= foo_prob(x,False).
    def stay_prob(self, unit, bias):
        ''' How likely a unit is to stay in the province indicated.
        '''#'''
        result = ((1 - self.dislodge_prob(unit, not bias))
                * (1 - self.move_prob(unit, not bias)))
    def dislodge_prob(self, unit, bias):
        ''' How likely the indicated unit is to be dislodged unless it moves.
        '''#'''
        # if no more than one enemy unit nearby, 0
        # if all nearby enemy units are attacked, 0
        return bias and 1 or 0
    def move_prob(self, unit, bias):
        ''' How likely a unit is to move out of the province indicated.
        '''#'''
        order = self.unit_orders.getdefault(unit.key, None)
        if order:
            if order.is_moving(): result = success_prob(order, bias)
            else: result = 0
        else: return bias and 1 or 0
    def destroy_prob(self, unit, bias):
        ''' How likely the given unit is to be destroyed.
        '''#'''
        return bias and 1 or 0
    def threat_prob(self, centre, bias):
        ''' How likely the given supply center is to have an enemy closer than a friend.
        '''#'''
        return bias and 1 or 0
    def lost_prob(self, province, bias):
        ''' How likely the given province is to be taken by an enemy.
        '''#'''
        return bias and 1 or 0
    def success_prob(self, order, bias):
        ''' How likely the given order is to succeed.
        '''#'''
        return bias and 1 or 0
    
    # Cache results of the probability functions
    stay_prob = Memoize(stay_prob)
    move_prob = Memoize(move_prob)
    lost_prob = Memoize(lost_prob)
    threat_prob = Memoize(threat_prob)
    success_prob = Memoize(success_prob)
    destroy_prob = Memoize(destroy_prob)
    dislodge_prob = Memoize(dislodge_prob)


if __name__ == "__main__":
    import main
    main.run_player(ComboBot)

# vim: sts=4 sw=4 et tw=75 fo=crql1
