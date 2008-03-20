''' DumberBot - A Python version of David Norman's DumbBot
    Copyright (C) 2003-2008  David Norman and Eric Wald
    
    This software may be reused for non-commercial purposes without charge,
    and without notifying the authors.  Use of any part of this software for
    commercial purposes without permission from the authors is prohibited.
'''#'''

from copy   import copy
from random import randint, random, shuffle
from time   import ctime

from parlance.config    import Configuration, stringlist
from parlance.functions import defaultdict, expand_list
from parlance.gameboard import Unit
from parlance.orders    import *
from parlance.player    import Player
from parlance.tokens    import AUT, FAL, SPR, SUM, UNO, WIN

# The number of values in the proximity weightings
PROXIMITY_DEPTH = 10

class DumbBot_Values(Configuration):
    ''' Various constants that affect how the bot plays.
        These are the values used by the original DumbBot;
        there has been no attempt to optimise them for best play.
        A few of these values enable features not available to DumbBot;
        the default values for these disable them.
    '''#'''
    def intlist(self, value):
        ''' Parser for a list of integers.'''
        strings = stringlist(value)
        try: result = map(int, strings)
        except ValueError:
            raise ValueError('Invalid list of integers')
        return result
    
    __options__ = (
        ('proximity_spring_attack_weight', int, 700, 'spring attack',
            "Importance of attacking centres we don't own, in Spring"),
        
        ('proximity_spring_defence_weight', int, 300, 'spring defence',
            "Importance of defending our own centres in Spring"),
        
        ('proximity_fall_attack_weight', int, 600, 'fall attack',
            "Importance of attacking centres we don't own, in Fall"),
        ('proximity_fall_defence_weight', int, 400, 'fall defence',
            "Importance of defending our own centres in Fall"),
        
        ('spring_proximity_weight', intlist,
            [100, 1000, 30, 10, 6, 5, 4, 3, 2, 1], 'spring proximity',
            "Importance of proximity[n] in Spring"),
        
        ('spring_strength_weight', int, 1000, 'spring strength',
            "Importance of our attack strength on a province in Spring"),
        
        ('spring_competition_weight', int, 1000, 'spring competition',
            "Importance of lack of competition for the province in Spring"),
        
        ('fall_proximity_weight', intlist,
            [1000, 100, 30, 10, 6, 5, 4, 3, 2, 1], 'fall proximity',
            "Importance of proximity[n] in Fall"),
        
        ('fall_strength_weight', int, 1000, 'fall strength',
            "Importance of our attack strength on a province in Fall"),
        
        ('fall_competition_weight', int, 1000, 'fall competition',
            "Importance of lack of competition for the province in Fall"),
        
        ('base_unit_weight', int, 0, 'unit attack',
            "Importance of attacking opposing units"),
        
        ('home_vacation_weight', int, 0, 'home vacation',
            "Importance of vacating unattacked home SCs"),
        
        ('home_attack_weight', int, 1, 'home attack',
            "Importance of attacking another power's home supply centers"),
        
        ('home_defence_weight', int, 1, 'home defence',
            "Importance of defending or regaining our own home supply centers"),
        
        ('build_defence_weight', int, 1000, 'build defence',
            "Importance of building in provinces we need to defend"),
        
        ('build_proximity_weight', intlist,
            [1000, 100, 30, 10, 6, 5, 4, 3, 2, 1], 'build proximity',
            "Importance of proximity[n] when building"),
        
        ('remove_defence_weight', int, 1000, 'remove defence',
            "Importance of removing in provinces we don't need to defend"),
        
        ('remove_proximity_weight', intlist,
            [1000, 100, 30, 10, 6, 5, 4, 3, 2, 1], 'remove proximity',
            "Importance of proximity[n] when removing"),
        
        ('play_alternative', int, 50, 'play alternative',
            "Percentage change of not automatically playing the best move"),
        
        ('alternative_difference_modifier', int, 500, 'alternative modifier',
            'If not automatic, chance of playing best move',
            'if inferior move is nearly as good.',
            "Larger numbers mean less chance."),
        
        # Formula for power size.
        ('size_square_coefficient', int, 1, 'square coefficient',
            "A in S = Ax^2 + Bx + C, where x is centre count and S is size of power"),
        ('size_coefficient', int, 4, 'size coefficient',
            "B in S = Ax^2 + Bx + C, where x is centre count and S is size of power"),
        ('size_constant', int, 16, 'size constant',
            "C in S = Ax^2 + Bx + C, where x is centre count and S is size of power"),
        
        ('convoy_weight', int, 0, 'convoy weight',
            "Percentage value a convoy has compared to a comparable move.",
            "0 prevents convoys; 100 gives them equal weight."),
    )
    
    def mutate(self, factor):
        ''' Create and return a mutated version of this set of values.
            Higher values of factor indicate greater degrees of mutation.
        '''#'''
        def tweak(value):
            x = int(abs(value * factor)) + 1
            return value + randint(-x,x)
        mutant = copy(self)
        for klass in self.__class__.__mro__:
            for item in getattr(klass, '__options__', ()):
                name = item[0]
                option_type = item[1]
                if option_type is int:
                    setattr(mutant, name, tweak(getattr(self, name)))
                elif option_type is self.intlist:
                    values = [tweak(value) for value in getattr(self, name)]
                    setattr(mutant, name, values)
        return mutant
    
    def __str__(self):
        values = (str(getattr(self, item[0])) for item in self.__options__)
        return self.__class__.__name__ + '(' + str.join(', ', values) + ')'

class Province_Values(object):
    ''' Holds various information about the provinces.
        This needs to be separate from the Map, so generate_orders()
        can be re-entrant (in case it runs overtime).
        
        - proximity_map         prov -> list of PROXIMITY_DEPTH values; the value of the province, considering the N nearest spaces
        - defence_value         prov -> approximately the size of the largest enemy who has a unit next to the province
        - attack_value          prov -> approximately the size of the owning power
        - strength_value        prov -> the number of units we have next to the province
        - competition_value     prov -> the greatest number of units any other power has next to the province
        - adjacent_units        prov -> nation -> Units the nation has in or next to the province
    '''#'''
    def __init__(self, board):
        provs = board.spaces.keys()
        self.defence_value     = dict.fromkeys(provs, 0)
        self.attack_value      = dict.fromkeys(provs, 0)
        self.strength_value    = dict.fromkeys(provs, 0)
        self.competition_value = dict.fromkeys(provs, 0)
        self.proximity_map     = defaultdict(lambda: [0] * PROXIMITY_DEPTH)
        self.adjacent_units    = defaultdict(lambda: defaultdict(list))

class DumbBot(Player):
    ''' A mimic of David Norman's DumbBot.
        From the original C file:
        /**
         * How it works.
         *
         * DumbBot works in two stages. In the first stage it calculates a value
         * for each province and each coast. Then in the second stage, it works
         * out an order for each unit, based on those values.
         *
         * For each province, it calculates the following:
         * 
         * - If it is our supply centre, the size of the largest adjacent power
         * - If it is not our supply centre, the size of the owning power
         * - If it is not a supply centre, zero.
         *
         * Then
         *
         * Proximity[0] for each coast is the above value, multiplied by a weighting.
         *
         * Then
         *
         * Proximity[n] for each coast = ( sum( proximity[ n-1 ] for all adjacent coasts
         *                                 * proximity[ n-1 ] for this coast )
         *                               / 5
         *
         * Also for each province, it works out the strength of attack we have
         * on that province - the number of adjacent units we have, and the
         * competition for that province - the number of adjacent units any one
         * other power has.
         *
         * Finally it works out an overall value for each coast, based on all
         * the proximity values for that coast, and the strength and competition
         * for that province, each of which is multiplied by a weighting
         *
         * Then for move orders, it tries to move to the best adjacent coast,
         * with a random chance of it moving to the second best, third best, etc
         * (with that chance varying depending how close to first the second
         * place is, etc). If the best place is where it already is, it holds.
         * If the best place already has an occupying unit, or already has a
         * unit moving there, it either supports that unit, or moves elsewhere,
         * depending on whether the other unit is guaranteed to succeed or not.
         *
         * Retreats are the same, except there are no supports...
         *
         * Builds and Disbands are also much the same - build in the highest
         * value home centre disband the unit in the lowest value location.
         **/
    '''#'''
    
    __options__ = (
        ('print_csv', bool, False, None,
            'Whether to print a statistics file every turn, with province values.'),
    )
    
    def __init__(self, values=None, **kwargs):
        self.__super.__init__(**kwargs)
        self.vals = values or DumbBot_Values()
        self.log_debug(9, '%s (%s); started at %s',
                self.name, self.version, ctime())
        self.attitude = defaultdict(lambda: 1)
    def handle_SCO(self, message):
        ''' Stores the size of each power,
            modified by the Ax^2 + Bx + C formula from DumbBot_Values.
        '''#'''
        self.log_debug(7, 'Setting power_size matrix')
        self.power_size = {UNO: self.vals.size_constant}
        for power_counter, power in self.map.powers.iteritems():
            size = len(power.centers)
            self.power_size[ power_counter ] = (
                self.vals.size_square_coefficient * size * size
                + self.vals.size_coefficient * size
                + self.vals.size_constant
            ) * self.attitude[ power_counter ]
    
    def generate_orders(self):
        ''' Create and send orders for the phase.
            Warning: This function is executed in a separate thread.
            This means that it won't kill the whole bot on errors,
            but it might get called again before completing.
        '''#'''
        turn   = self.map.current_turn
        season = turn.season
        phase  = turn.phase()
        orders = values = None
        
        try:
            self.log_debug(10, 'Starting NOW %s message', turn)
            if not (self.in_game and self.missing_orders()): return
            if   season in (SPR, SUM):
                # Spring Moves/Retreats
                values = self.calculate_factors( self.vals.proximity_spring_attack_weight, self.vals.proximity_spring_defence_weight )
                self.calculate_destination_value( values, self.vals.spring_proximity_weight, self.vals.spring_strength_weight, self.vals.spring_competition_weight )
            elif season in (FAL, AUT):
                # Fall Moves/Retreats
                values = self.calculate_factors( self.vals.proximity_fall_attack_weight, self.vals.proximity_fall_defence_weight )
                self.calculate_destination_value( values, self.vals.fall_proximity_weight, self.vals.fall_strength_weight, self.vals.fall_competition_weight )
            elif season is not WIN:
                self.log_debug(1, 'Unknown season %s', season)
            
            if   phase == turn.move_phase:    orders = self.generate_movement_orders(values)
            elif phase == turn.retreat_phase: orders = self.generate_retreat_orders(values)
            elif phase == turn.build_phase:
                values = self.calculate_factors( self.vals.proximity_spring_attack_weight, self.vals.proximity_spring_defence_weight )
                surplus = self.power.surplus()
                self.log_debug(11, ' Build phase surplus: %d', surplus)
                if surplus > 0:
                    # Removing excess units
                    self.calculate_winter_destination_value( values, self.vals.remove_proximity_weight, self.vals.remove_defence_weight )
                    orders = self.generate_remove_orders(surplus, values)
                elif surplus < 0:
                    # Building
                    self.calculate_winter_destination_value( values, self.vals.build_proximity_weight, self.vals.build_defence_weight )
                    orders = self.generate_build_orders(-surplus, values)
            else: self.log_debug(1, 'Unknown phase %s', phase)
            
            if orders: self.submit_set(orders)
            if self.options.print_csv: self.generate_csv(values);
        except:
            self.log_debug(1, 'Error while handling NOW %s message', turn)
            if values: self.generate_csv(values)
            self.close()
            raise
    def calculate_factors(self, proximity_attack_weight, proximity_defence_weight):
        values = Province_Values(self.map)
        
        for province_counter in self.map.spaces.itervalues():
            # Calculate attack and defense values for each province
            if province_counter.is_supply():
                if self.friendly(province_counter.owner):
                    # Our SC. Calc defense value
                    values.defence_value[province_counter.key] = self.calculate_defence_value( province_counter )
                else:
                    # Not ours. Calc attack value (which is the size of the owning power)
                    owner = province_counter.owner
                    if owner:
                        values.attack_value[province_counter.key] = self.power_size[owner.key]
                        if owner in province_counter.homes:
                            values.attack_value[province_counter.key] *= self.vals.home_attack_weight
                    else: values.attack_value[province_counter.key] = self.vals.size_constant
            for unit in province_counter.units:
                values.attack_value[province_counter.key] += self.power_size[unit.nation.key] * self.vals.base_unit_weight // 100
            
            # Calculate proximity[0] for each coast.
            # Proximity[0] is calculated based on the attack value and defence value of the province,
            # modified by the weightings for the current season.
            for province_coast_iterator in province_counter.coasts:
                values.proximity_map[province_coast_iterator.key] = [
                    values.attack_value[province_counter.key] * proximity_attack_weight +
                    values.defence_value[province_counter.key] * proximity_defence_weight
                ]
        
        # Calculate proximities [ 1... ]
        # proximity[n] = ( sum of proximity[n-1] for this coast plus all coasts
        # which this coast is adjacent to ) / 5
        # The divide by 5 is just to keep all values of proximity[ n ] in the same range.
        # The average coast has 4 adjacent coasts, plus itself.
        for proximity_counter in range(PROXIMITY_DEPTH - 1):
            for proximity_iterator in self.map.coasts.itervalues():
                provs_seen = {}
                # Collect the weight of each adjacent coast,
                # but only the highest from a single province
                for coast_iterator in proximity_iterator.borders_out:
                    coast = self.map.coasts[coast_iterator]
                    weight = values.proximity_map[coast.key][proximity_counter]
                    key = coast.province.key
                    if provs_seen.has_key(key):
                        if weight > provs_seen[key]: provs_seen[key] = weight
                    else: provs_seen[key] = weight
                
                # Add this province in, then divide the answer by 5
                values.proximity_map[proximity_iterator.key].append(sum(provs_seen.values(),
                    values.proximity_map[proximity_iterator.key][proximity_counter]) // 5)
        
        # Find the units each power has in or next to each province
        for unit_iterator in self.map.units:
            values.adjacent_units[unit_iterator.coast.province.key][ unit_iterator.nation.key ].append(unit_iterator)
            for coast_iterator in unit_iterator.coast.borders_out:
                values.adjacent_units[ coast_iterator[1] ][ unit_iterator.nation.key ].append(unit_iterator)
        
        for province_counter in self.map.spaces:
            for power_counter in self.map.powers:
                unit_count = len(values.adjacent_units[province_counter][ power_counter ])
                if self.friendly(power_counter):
                    values.strength_value[province_counter] = unit_count
                elif unit_count > values.competition_value[province_counter]:
                    values.competition_value[province_counter] = unit_count
        
        return values
    def calculate_defence_value(self, province):
        ''' Calculate the defense value. The defence value of a centre
            is the size of the largest enemy who has a unit which can
            move into the province, multiplied by a small factor
            if it is one of our home centres.
        '''#'''
        
        defence_value = 0
        self.log_debug(11, ' Calculating defence for %s', province)
        for prov in province.borders_in:
            for unit in self.map.spaces[prov].units:
                self.log_debug(13, '  Unit in %s: %s', prov, unit)
                if (not self.friendly(unit.nation)
                        and self.power_size[unit.nation.key] > defence_value
                        and unit.can_move_to(province)):
                    defence_value = self.power_size[unit.nation.key]
                    self.log_debug(13, '   Setting defence to %f', defence_value)
        if self.power.key in province.homes:
            if defence_value: defence_value *= self.vals.home_defence_weight
            else: defence_value = -self.vals.home_vacation_weight
        return defence_value
    def calculate_destination_value(self, values, proximity_weight, strength_weight, competition_weight):
        ''' Given the province and coast calculated values, and the
            weighting for this turn, calculate the value of each coast.
        '''#'''
        destination_value = {}
        for coast_id in self.map.coasts.itervalues():
            destination_weight = 0
            for proximity_counter in range(PROXIMITY_DEPTH):
                destination_weight += values.proximity_map[coast_id.key][ proximity_counter ] * proximity_weight[ proximity_counter ]
            destination_weight += strength_weight    * values.strength_value[coast_id.province.key]
            destination_weight -= competition_weight * values.competition_value[coast_id.province.key]
            destination_value[coast_id.key] = destination_weight
        values.destination_value = destination_value
    def calculate_winter_destination_value(self, values, proximity_weight, defence_weight):
        ''' Given the province and coast calculated values, and the
            weighting for this turn, calculate the value of each coast
            for winter builds and removals.
        '''#'''
        destination_value = {}
        for coast_id in self.map.coasts.itervalues():
            destination_weight = 0
            for proximity_counter in range(PROXIMITY_DEPTH):
                destination_weight += values.proximity_map[coast_id.key][ proximity_counter ] * proximity_weight[ proximity_counter ]
            destination_weight += defence_weight * max(0, values.defence_value[coast_id.province.key])
            destination_value[coast_id.key] = destination_weight
        values.destination_value = destination_value
    def generate_csv(self, values):
        ''' Generate a .csv file (readable by Excel and most other
            spreadsheets) which shows the data used to calculate the moves
            for this turn. Lists all the calculated information for every
            province we have a unit in or adjacent to.
        '''#'''
        filename = "log/bots/%s_%d_%s.csv" % (
            self.power,
            self.map.current_turn.year,
            self.map.current_turn.season
        )
        try: fp = open(filename, "w")
        except IOError: self.log_debug(1, "Couldn't open csv file " + filename)
        else:
            max_proximity = PROXIMITY_DEPTH
            fp.write("Province,Coast,Attack,Defence,Strength,Competition,")
            for proximity_counter in range(max_proximity):
                fp.write("Proximity[%d]," % proximity_counter)
            fp.write("Value\n")
            for coast_id in self.map.coasts.itervalues():
                if values.strength_value[coast_id.province.key] > 0:
                    fp.write("%s,%s, " % (coast_id.province, coast_id))
                    fp.write("%2f,%2f,%f,%f, " % (
                        values.attack_value[coast_id.province.key],
                        values.defence_value[coast_id.province.key],
                        values.strength_value[coast_id.province.key],
                        values.competition_value[coast_id.province.key]
                    ))
                    
                    for proximity_counter in range(max_proximity):
                        if len(values.proximity_map[coast_id.key]) > proximity_counter:
                            fp.write("%5f," % values.proximity_map[coast_id.key][ proximity_counter ])
                        else: fp.write("oops,")
                    fp.write(" %8f" % values.destination_value[coast_id.key])
                    fp.write("\n")
            fp.close()
    
    def friendly(self, nation): return nation == self.power
    def generate_movement_orders(self, values):
        ''' Generate the actual orders for a movement turn.'''
        self.log_debug(10, "Movement orders for %s" % self.map.current_turn)
        orders = self.dumb_movement(values, OrderSet(), self.power.units)
        self.check_for_wasted_holds(orders, values)
        return orders
    def dumb_movement(self, values, orders, units):
        waiting = defaultdict(list)
        our_units = list(units)
        
        while our_units:
            # Put our units into a random order. This is one of the ways
            # in which DumbBot is made non-deterministic - the order
            # in which the units are considered can affect the orders selected
            shuffle(our_units)
            unordered = []
            
            for unit in our_units:
                if not orders.get_order(unit):
                    order = self.order_unit(unit, orders, values, waiting)
                    if order: orders.add(order, unit.nation)
                    else: unordered.append(unit)
            our_units = unordered
        return orders
    def check_for_wasted_holds(self, orders, values):
        ''' Replaces Hold orders with supports, if possible.'''
        destination_map = {}
        holding = []
        for order in orders:
            if order.is_moving():
                destination_map[order.destination.province.key] = (order,
                    values.destination_value[order.destination.key] *
                    values.competition_value[order.destination.province.key])
            else:
                destination_map[order.unit.coast.province.key] = (order,
                    values.destination_value[order.unit.coast.key] *
                    (values.competition_value[order.unit.coast.province.key] - 1))
                if order.is_holding(): holding.append(order)
        
        for order in holding:
            unit = order.unit
            self.log_debug(13, " Reconsidering hold for %s." % unit)
            # Consider every province we can move to
            source = None
            max_destination_value = 0
            for adjacent_province in [self.map.coasts[coast].province
                    for coast in unit.coast.borders_out]:
                this_source = destination_map.get(adjacent_province.key, None)
                if this_source:
                    # Unit is moving or holding there
                    this_value = this_source[1]
                    if this_value > max_destination_value or not source:
                        # Best so far
                        source = this_source[0]
                        max_destination_value = this_value
            
            if source:
                # Found something worth supporting
                self.log_debug(11, "  Overriding hold order in %s with support to %s",
                    unit.coast.province, source.unit)
                self.log_debug(14, "   Trying to remove '%s' from %s", order, orders)
                orders.remove(order)
                if source.is_moving():
                    orders.add(SupportMoveOrder(unit, source.unit, source.destination), unit.nation)
                else: orders.add(SupportHoldOrder(unit, source.unit), unit.nation)
                self.log_debug(14, "   Now have orders = %s", orders)
    def order_unit(self, unit, orders, values, waiting):
        self.log_debug(11, " Selecting destination for %s", unit)
        
        # Determine whether another unit is waiting on this one
        waiters = waiting[unit.coast.province.key]
        
        # Put all the adjacent coasts into the destination map,
        # and the current location (we can hold rather than move)
        destination_map = [unit.coast.key] + [key
            for key in unit.coast.borders_out
            if key[1] not in waiters]
        
        while True:
            # Pick a destination
            dest = self.random_destination(destination_map, values)
            self.log_debug(11, "  Destination selected: %s" % dest)
            
            # If this is a hold order
            if dest.province == unit.coast.province:
                convoy_order = self.consider_convoy(unit, orders, values)
                if convoy_order: return convoy_order
                else:
                    # Hold order
                    self.log_debug(11, "  Ordered to hold")
                    return HoldOrder(unit)
            else:
                # Check whether this is a reasonable selection
                selection_is_ok = True
                
                # If we have a unit in this province already 
                for other_unit in dest.province.units:
                    if self.friendly(other_unit.nation):
                        self.log_debug(13, "  Province occupied")
                        
                        # Check whether it has been ordered already
                        order = orders.get_order(other_unit)
                        if order:
                            if order.is_moving():
                                # Continue to the next check
                                self.log_debug(13, "   Occupying unit moving out")
                            else:
                                self.log_debug(13, "   Occupying unit not moving")
                                # If it needs supporting
                                if values.competition_value[dest.province.key] > 1:
                                    # Support it
                                    self.log_debug(11, "    Supporting occupying unit")
                                    return SupportHoldOrder(unit, other_unit)
                                else: selection_is_ok = False
                        elif other_unit.nation != self.power:
                            # The other unit is friendly, but we can't
                            # guarantee its move.  Go somewhere else.
                            self.log_debug(13, "   Occupying unit friendly")
                            selection_is_ok = False
                        else:
                            # We can't decide whether to move there or not,
                            # so give up on this unit for now,
                            # but signal the other unit not to try moving here.
                            self.log_debug(13, "   Occupying unit unordered")
                            waiting[dest.province.key].append(unit.coast.province.key)
                            return None
                
                # Check for units moving there
                self.log_debug(13, "  Checking for %s in order destinations", dest.province.key)
                for order in orders.moving_into(dest.province):
                    self.log_debug(13, "   Unit already moving here")
                    # If it may need support
                    if values.competition_value[dest.province.key] > 0:
                        # Support it
                        self.log_debug(11, "    Supporting moving unit")
                        return SupportMoveOrder(unit, order.unit, order.destination)
                    else: selection_is_ok = False
                
                if selection_is_ok:
                    # Final check: see if a convoy would be better than a direct move
                    convoy_order = self.consider_convoy(unit, orders, values, dest)
                    if convoy_order: return convoy_order
                    else:
                        self.log_debug(11, "  Ordered to move")
                        return MoveOrder(unit, dest)
                else:
                    self.log_debug(13, "  Destination not accepted")
                    # Make sure it isn't selected again
                    destination_map.remove(dest.key)
        return None
    def consider_convoy(self, fleet, orders, values, dest=None):
        if self.vals.convoy_weight > 0 and fleet.can_convoy():
            self.log_debug(13, "  Considering convoys through %s." % fleet)
            beach = None
            if dest:
                key = dest.province.is_coastal()
                if key: beach = self.map.coasts[key]
                else: self.log_debug(13, "   Selected location not coastal.")
            else:
                coasts = self.map.coasts
                possible = []
                for border in fleet.coast.borders_out:
                    prov = coasts[border].province
                    if not orders.moving_into(prov):
                        for unit in prov.units:
                            # Don't land on our holding or unsure unit.
                            # Side effect: prevents convoying a unit to itself.
                            if not (self.friendly(unit.nation)
                                    and not orders.is_moving(unit)):
                                key = prov.is_coastal()
                                if key: possible.append(key)
                if possible:
                    beach = self.random_destination(possible, values)
                    self.log_debug(13, "   %s selected for landing." % beach.province)
                else: self.log_debug(13, "   No available landing sites.")
            
            if beach:
                # The last two conditions deserve explanation:
                # If it has already been ordered, we run the risk of an
                # inconsistent order set.  If it can move there anyway,
                # a support is usually better than a convoy.
                # (Granted, that could be the solution to BUL/CON...)
                armies = [unit.coast.key for unit in self.map.units
                    if unit.can_be_convoyed()
                    and self.friendly(unit.nation)
                    and fleet.can_move_to(unit.coast.province)
                    and not orders.get_order(unit)
                    and not unit.can_move_to(beach.province.key)]
                if armies:
                    # Consider the army we least want to keep in place.
                    army = self.random_source(armies, values)
                    self.log_debug(13, '   %s chosen (from among %s).' % (army,
                        expand_list([key[1] for key in armies])))
                    if dest: alternate = fleet.coast
                    else: alternate = beach
                    convoy_value = values.destination_value[alternate.key] * self.vals.convoy_weight
                    army_value = values.destination_value[army.key]
                    convoy_best = army_value < convoy_value
                    if convoy_best: first = convoy_value; second = army_value
                    else: first = army_value; second = convoy_value
                    
                    if convoy_best != self.weighted_choice(first, second):
                        self.log_debug(11, "   Ordered to convoy")
                        unit = [u for u in self.map.units if u.coast.key == army.key][0]
                        orders.add(ConvoyedOrder(unit, beach, [fleet]), unit.nation)
                        return ConvoyingOrder(fleet, unit, beach)
                    else: self.log_debug(13, "   Convoy rejected")
                else: self.log_debug(13, "   Nobody available to convoy")
        return None
    
    def generate_retreat_orders(self, values):
        ''' Generate Retreat orders'''
        self.log_debug(10, "Retreat orders for %s", self.map.current_turn)
        orders = OrderSet(self.power)
        
        # Put the units into a list in random order
        our_units = [unit for unit in self.power.units if unit.dislodged]
        shuffle(our_units)
        for unit in our_units:
            self.log_debug(13, " Selecting destination for %s", unit)
            # Todo: Consider whether rebuilding would be better,
            # if the next phase is winter
            
            # Put all the possible retreats into the destination map
            destination_map = [key for key in unit.coast.borders_out
                    if key[1] in unit.retreats]
            
            while destination_map:
                # Pick a destination
                dest = self.random_destination(destination_map, values)
                self.log_debug(13, "  Destination selected: %s", dest)
                
                # If there is a unit already moving to this province
                if orders.moving_into(dest.province):
                    self.log_debug(13, "   Unit already moving here")
                    # Todo: Compare retreat values between units
                    
                    # Avoid choosing this coast again
                    destination_map.remove(dest.key)
                else:
                    # Order the retreat
                    self.log_debug(13, "   Ordered to retreat")
                    orders.add(RetreatOrder(unit, dest))
                    break
            else:
                # No retreat possible. Disband unit
                self.log_debug(13, "   Disbanding unit")
                orders.add(DisbandOrder(unit))
        return orders
    def generate_remove_orders(self, remove_count, values):
        ''' Generate the actual remove orders for an adjustment phase'''
        self.log_debug(10, "Remove orders for %s", self.map.current_turn)
        orders = OrderSet(self.power)
        
        # Put all the units into a removal map
        remove_map = self.power.units[:]
        
        # For each required removal
        while remove_count and remove_map:
            unit = remove_map.pop(self.random_selection([
                    -values.destination_value[u.coast.key]
                    for u in remove_map]))
            self.log_debug(11, " Removal selected: %s", unit)
            orders.add(RemoveOrder(unit))
            remove_count -= 1
        return orders
    def generate_build_orders(self, build_count, values):
        ''' Generate the build orders for an adjustment turn'''
        self.log_debug(10, "Build orders for %s", self.map.current_turn)
        orders = OrderSet(self.power)
        
        # Put all the coasts of our open home centres into a map
        self.log_debug(11, ' Choosing from coasts of %s.', expand_list(self.power.homes))
        build_map = [coast.key
            for prov in [self.map.spaces[p] for p in self.power.homes]
            if prov.owner == self.power and not prov.units
            for coast in prov.coasts]
        
        # For each build, while we have a vacant home centre
        builds_remaining = build_count
        while build_map and builds_remaining:
            # Select the best location, more or less
            dest = self.random_destination(build_map, values)
            self.log_debug(13, " Considering build: %s", dest)
            build_map.remove(dest.key)
            
            if orders.has_order(dest.province):
                self.log_debug(13, '  Already building in %s', dest.province)
            else:
                self.log_debug(11, '  Ordering build')
                orders.add(BuildOrder(Unit(self.power, dest)))
                builds_remaining -= 1
        
        # If not all builds ordered, order some waives.
        if builds_remaining:
            self.log_debug(11, " Waiving %d builds", builds_remaining)
            orders.waive(builds_remaining)
        return orders
    
    def random_source(self, coast_keys, values):
        ''' Chooses randomly among the coasts,
            with preference to lower values of values.destination_value.
        '''#'''
        keys = [values.destination_value[key] for key in coast_keys]
        best = 2 * max(keys)
        vals = [best - key for key in keys]
        return self.map.coasts[coast_keys[self.random_selection(vals)]]
    def random_destination(self, coast_keys, values):
        ''' Chooses randomly among the coasts,
            with preference to higher values of values.destination_value.
        '''#'''
        return self.map.coasts[coast_keys[self.random_selection(
                [values.destination_value[key] for key in coast_keys])]]
    def random_selection(self, choice_values):
        ''' Chooses randomly among the choices,
            using the first most of the time, particularly if much better.
            Returns the index of the chosen item.
        '''#'''
        sorted_values = [(v,i) for (i,v) in enumerate(choice_values)]
        sorted_values.sort()
        iterator = best = current = len(sorted_values) - 1
        
        while iterator > 0:
            iterator -= 1
            if self.weighted_choice(sorted_values[best][0],
                    sorted_values[iterator][0]):
                current = iterator
                # The original DumbBot checks against the current selection.
                # To be a truly faithful mimic, uncomment the next line.
                #best = current
            else: break
        return sorted_values[current][1]
    def weighted_choice(self, best_choice, second_choice):
        ''' Chooses randomly between first- and second-choice destinations,
            using the first most of the time, particularly if much better.
            Returns True for second choice, False for best.
        '''#'''
        # Warning: variable names are backwards here.
        m_play_alternative = self.vals.play_alternative
        use_next = False
        
        # The chance of using the best value if not automatic.
        # Due to the difference modifier, this may end up greater than 100.
        if best_choice:
            best_chance = (
                (best_choice - second_choice)
                * self.vals.alternative_difference_modifier
                // abs(best_choice)
            )
        else: best_chance = 0
        
        # This is actually the code from David's log_debug statement,
        # but it seems to match what was originally here.
        # This is the chance of using the second-best alternative.
        chance = m_play_alternative - (best_chance * m_play_alternative // 100)
        if random() * 100 < chance:
            use_next = True
            choice = 'Second'
        else: choice = 'First'
        
        self.log_debug(14, "     %s choice selected (%d%% chance of %d over %d)",
            choice, chance, second_choice, best_choice)
        
        return use_next
    
    # Hooks for mutation
    def get_values(self): return self.vals


def run():
    from parlance.main import run_player
    run_player(DumbBot)
