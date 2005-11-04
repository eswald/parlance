''' DAIDE Gameboard Classes
    Defines classes to represent parts of the Diplomacy game.
'''#'''

import config
from operator    import lt, gt
from functions   import any, all, autosuper, Comparable
from iaq         import DefaultDict
from gameboard   import Turn, Power, Coast, Unit
from language    import *
#from language    import Message, \
#MIS, SUB, WVE, REM, BLD, DSB, RTO, CTO, CVY, SUP, MTO, HLD, VIA, \
#MBV, NMR, NMB, ESC, HSC, YSC, NSC, CST, NSU, NYU, NRS, NVR, NRN, \
#FAR, NSP, NSF, NAS, NSA


class UnitOrder(Comparable):
    ''' Abstract base class for all types of orders.'''
    __metaclass__ = autosuper
    order_type = None
    destination = None   # Coast where the unit expects to end up
    order = None         # The order as originally issued
    unit = None          # The Unit being ordered
    key = None           # The order's essential parts
    
    def __str__(self):
        return '%s %s %s' % (self.unit.coast.unit_type,
                self.unit.coast.province, self.order_type)
    def tokenize(self): return self.order or Message(self.key)
    def __cmp__(self, other): return cmp(self.key, other.key)
    def create(klass, order, nation, board, datc):
        result = klass(board.ordered_unit(nation, order[0]))
        result.order = order
        return result
    create = classmethod(create)
    
    # Order queries
    def is_moving(self):     return self.order_type in (MTO, CTO, RTO)
    def is_holding(self):    return self.order_type == HLD
    def is_supporting(self): return self.order_type == SUP
    def is_convoying(self):  return self.order_type == CVY
    def is_convoyed(self):   return self.order_type == CTO
    def is_leaving(self):    return self.order_type in (MTO, CTO, RTO, DSB, REM)
    def moving_to(self, province):
        return self.is_moving() and province == self.destination.province
    def matches(self, order_set): return True
    def maybe_overland(self): return False
    def order_note(self, power, phase, past_orders=None):
        ''' Returns a Token representing the legality of the order.
            - MBV: Order is OK
            - FAR: Not adjacent
            - NSP: No such province
            - NSU: No such unit
            - NAS: Not at sea (for a convoying fleet)
            - NSF: No such fleet (in VIA section of CTO
                   or the unit performing a CVY)
            - NSA: No such army (for unit being ordered to CTO
                   or for unit being CVYed)
            - NYU: Not your unit
            - NRN: No retreat needed for this unit
            - NVR: Not a valid retreat space
            - YSC: Not your supply centre
            - ESC: Not an empty supply centre
            - HSC: Not a home supply centre
            - NSC: Not a supply centre
            - CST: No coast specified for fleet build in bicoastal province,
                   or an attempt to build a fleet inland, or an army at sea.
            - NMB: No more builds allowed
            - NMR: No more removals allowed
            - NRS: Not the right season
        '''#'''
        note = MBV
        if not (self.order_type.value() & phase):   note = NRS
        elif self.unit.nation != power:             note = NYU
        elif not self.unit.coast.province.exists(): note = NSP
        elif not self.unit.exists():                note = NSU
        elif self.destination:
            if not self.destination.province.exists(): note = NSP
            elif not self.unit.exists():                note = NSU
        return note

class MovementPhaseOrder(UnitOrder):
    def convoy_note(convoyed, destination, route_valid=bool):
        result = FAR
        if not (convoyed.exists() and convoyed.can_be_convoyed()): result = NSA
        elif destination.province.is_coastal():
            routes = convoyed.coast.routes[destination.province.key]
            def has_fleet(sea): return len(sea.units) > 0
            for sea_list in routes:
                if route_valid(sea_list) and all(sea_list, has_fleet):
                    result = MBV
                    break
        #print 'convoy_note(%s, %s) => %s' % (convoyed, destination, result)
        return result
    convoy_note = staticmethod(convoy_note)
    def get_routes(self, convoyers, ignore_foreign):
        if self.unit.can_be_convoyed():
            if self.path:
                path_list = [[fleet.coast.province for fleet in self.path]]
            else: path_list = self.unit.coast.routes.get(self.destination.province.key)
            if path_list:
                key = self.unit.key
                def available(prov):
                    return convoyers.get(prov.key, (None, None))[0] == key
                all_routes = [path for path in path_list if all(path, available)]
                
                if ignore_foreign:
                    # DPTG craziness: ignore foreign convoyers if we can go alone.
                    nation = self.unit.nation
                    def countryman(prov):
                        return convoyers.get(prov.key, (None, None))[1] == nation
                    solo_routes = [path for path in all_routes if all(path, countryman)]
                else: solo_routes = None
                return (solo_routes or all_routes)
        return []
class HoldOrder(MovementPhaseOrder):
    order_type = HLD
    def __init__(self, unit):
        self.key = (unit.key, HLD)
        self.unit = unit
        self.destination = unit.coast
    def __repr__(self): return 'HoldOrder(%r)' % self.unit
class MoveOrder(MovementPhaseOrder):
    order_type = MTO
    path = None
    def __init__(self, unit, destination_coast, maybe_convoy=False):
        self.key = (unit.key, MTO, destination_coast.maybe_coast)
        self.unit = unit
        self.destination = destination_coast
        self.maybe_convoy = maybe_convoy
    def __str__(self):
        return '%s %s - %s' % (self.unit.coast.unit_type,
                self.unit.coast.province, self.destination.maybe_coast)
    def is_convoyed(self):    return self.maybe_convoy
    def maybe_overland(self): return self.maybe_convoy
    def order_note(self, power, phase, past_orders=None):
        note = self.__super.order_note(power, phase, past_orders)
        if note == MBV:
            if not self.unit.can_move_to(self.destination): note = FAR
            elif not self.destination.exists():             note = CST
        return note
    def create(klass, order, nation, board, datc):
        unit = board.ordered_unit(nation, order[0])
        dest = board.ordered_coast(unit, order[2], datc)
        if unit.can_be_convoyed() and datc.datc_4a3 != 'f':
            # Implicit convoys are allowed; check for them
            unit.coast.collect_convoy_routes(dest.province.key, board)
            if not unit.can_move_to(dest):
                # Can't move directly; attempt to convoy
                result = ConvoyedOrder(unit, dest)
            elif datc.datc_4a3 == 'e' or klass.convoy_note(unit, dest) != MBV:
                # DPTG: Only convoy adjacent if it's explicit
                # For other options, consider possible adjacent convoys
                result = klass(unit, dest)
            else: result = klass(unit, dest, True)
        else: result = klass(unit, dest)
        result.order = order
        return result
    create = classmethod(create)
class ConvoyingOrder(MovementPhaseOrder):
    order_type = CVY
    def __init__(self, unit, mover, destination):
        self.key = (unit.key, CVY, mover.key, CTO, destination.province.key)
        self.unit = unit
        self.supported = mover
        self.destination = destination
    def __str__(self):
        return '%s %s C %s - %s' % (
                self.unit.coast.unit_type, self.unit.coast.province,
                self.supported.coast.province, self.destination.province)
    def matches(self, order_set):
        ''' Whether the order is matched by the convoyed unit. '''
        counterpart = order_set.get_order(self.supported)
        return (self.supported.exists() and counterpart and counterpart.is_convoyed()
            and self.destination.matches(counterpart.destination.key))
    def order_note(self, power, phase, past_orders=None):
        note = self.__super.order_note(power, phase, past_orders)
        if note == MBV:
            if not self.unit.coast.province.can_convoy(): note = NAS
            elif not self.unit.can_convoy():              note = NSF
            else:
                def has_this_fleet(route, fleet=self.unit.coast.province.key):
                    return fleet in route
                note = self.convoy_note(self.supported, self.destination, has_this_fleet)
        return note
    def create(klass, order, nation, board, datc):
        unit = board.ordered_unit(nation, order[0])
        mover = board.ordered_unit(nation, order[2])
        dest = board.ordered_coast(mover, order[4], datc)
        mover.coast.collect_convoy_routes(dest.province.key, board)
        result = klass(unit, mover, dest)
        result.order = order
        return result
    create = classmethod(create)
class ConvoyedOrder(MovementPhaseOrder):
    order_type = CTO
    def __init__(self, unit, destination, path=None):
        # The path should be a list of Units (fleets), not provinces.
        # If the server supports pathless convoys, it may be omitted.
        self.unit = unit
        self.destination = destination
        self.path = None
        self.path_key = None
        if path: self.set_path(path)
        else: self.key = (unit.key, CTO, destination.province.key)
    def set_path(self, path):
        # Allows the server to send path specifications
        # even on orders that didn't originally have any.
        self.path = path
        self.path_key = tuple([fleet.coast.province.key for fleet in path])
        self.key = (self.unit.key, CTO, self.destination.province.key, VIA, self.path_key)
    def __str__(self):
        return '%s %s - %s - %s' % (
                self.unit.coast.unit_type, self.unit.coast.province,
                self.path and ' - '.join([str(u.coast.province) for u in self.path]) or '...',
                self.destination.maybe_coast)
    def matches(self, order_set):
        ''' Whether the order is matched by the convoying unit(s). '''
        def matching(fleet):
            counterpart = order_set.get_order(fleet)
            if counterpart:
                return (counterpart.is_convoying()
                        and counterpart.supported == self.unit
                        and counterpart.destination.matches(self.destination.key))
            return False
        if self.path: return all(self.path, matching)
        else: return True
    def order_note(self, power, phase, past_orders=None):
        note = self.__super.order_note(power, phase, past_orders)
        if note == MBV:
            note = self.convoy_note(self.unit, self.destination)
            if note == MBV and self.path:
                def real_prov(fleet): return fleet.coast.province.exists()
                def at_sea(fleet):    return fleet.coast.province.can_convoy()
                routes = self.unit.coast.routes[self.destination.province.key]
                if   not all(self.path, real_prov):        note = NSP
                elif not all(self.path, Unit.exists):      note = NSF
                elif not all(self.path, at_sea):           note = NAS
                elif not all(self.path, Unit.can_convoy):  note = NSF
                elif self.path_key not in routes:          note = FAR
        return note
    def create(klass, order, nation, board, datc):
        unit = board.ordered_unit(nation, order[0])
        dest = board.ordered_coast(unit, order[2], datc)
        if len(order) > 4:
            path = [board.ordered_unit(nation, prov) for prov in order[4]]
            #for prov in path: print 'Convoying unit: %s' % prov
        else: path = None
        unit.coast.collect_convoy_routes(dest.province.key, board)
        result = klass(unit, dest, path)
        result.order = order
        return result
    create = classmethod(create)

class SupportOrder(MovementPhaseOrder):
    order_type = SUP
    supported = None
    def order_note(self, power, phase, past_orders=None):
        note = self.__super.order_note(power, phase, past_orders)
        if note == MBV:
            if not self.supported.coast.province.exists():    note = NSP
            elif not self.supported.exists():                 note = NSU
            elif not self.unit.can_move_to(self.destination.province):
                note = FAR
        return note
    def create(order, nation, board, datc):
        # Note that we don't care about order[3], so it could be MTO or CTO.
        unit = board.ordered_unit(nation, order[0])
        supported = board.ordered_unit(nation, order[2])
        if len(order) > 4:
            dest = board.ordered_coast(supported, order[4], datc)
            legal_dest = True
            if supported.can_move_to(dest):
                if datc.datc_4b4 in 'abc' and not dest.exists():
                    # Coastline specifications are required
                    # Todo: Implement 'b' and 'c' fully.
                    legal_dest = False
                elif datc.datc_4b4 == 'e' and dest.coastline:
                    # Coastline specifications are ignored
                    dest = Coast(dest.unit_type, dest.province, None, [])
            else: supported.coast.collect_convoy_routes(dest.province.key, board)
            result = SupportMoveOrder(unit, supported, dest, legal_dest)
        else: result = SupportHoldOrder(unit, supported)
        result.order = order
        return result
    create = staticmethod(create)
class SupportHoldOrder(SupportOrder):
    def __init__(self, unit, holder):
        self.key = (unit.key, SUP, holder.key)
        self.unit = unit
        self.supported = holder
        self.destination = holder.coast
    def __str__(self):
        return '%s %s S %s' % (self.unit.coast.unit_type,
                self.unit.coast.province, self.supported.coast.province)
    def matches(self, order_set):
        ''' Whether the order is matched by the supported unit.
        '''#'''
        return (self.supported.exists()
                and not order_set.is_moving(self.supported)
                and self.supported.coast.province != self.unit.coast.province)
class SupportMoveOrder(SupportOrder):
    def __init__(self, unit, mover, destination, legal_coast=True):
        # Note: destination.maybe_coast would be better,
        # but is disallowed by the language.
        self.key = (unit.key, SUP, mover.key, MTO, destination.province.key)
        self.unit = unit
        self.supported = mover
        self.destination = destination
        self.legal = legal_coast
    def __str__(self):
        return '%s %s S %s - %s' % (
                self.unit.coast.unit_type, self.unit.coast.province,
                self.supported.coast.province, self.destination.province)
    def matches(self, order_set):
        ''' Whether the order is matched by the supported unit.'''
        counterpart = order_set.get_order(self.supported)
        return (self.supported.nation and counterpart.is_moving()
            and self.destination.matches(counterpart.destination.key))
    def order_note(self, power, phase, past_orders=None):
        # Note that the mover's destination need not exist: it could have
        # a coastline of None for a fleet moving to bicoastal.  However,
        # the province must exist, and both units must be able to move there.
        note = self.__super.order_note(power, phase, past_orders)
        if note == MBV:
            if self.supported.can_move_to(self.destination):
                if not self.legal: note = CST
            else:
                def has_not(route, prov=self.unit.coast.province.key):
                    return prov not in route
                result = self.convoy_note(self.supported, self.destination, has_not)
                if result != MBV: note = FAR
        return note

class RetreatPhaseOrder(UnitOrder):
    def order_note(self, power, phase, past_orders=None):
        note = self.__super.order_note(power, phase, past_orders)
        if note == MBV and not self.unit.dislodged: note = NRN
        return note
class DisbandOrder(RetreatPhaseOrder):
    order_type = DSB
    def __init__(self, unit):
        self.key = (unit.key, DSB)
        self.unit = unit
        self.destination = None
class RetreatOrder(RetreatPhaseOrder):
    order_type = RTO
    def __init__(self, unit, destination_coast):
        self.key = (unit.key, RTO, destination_coast.maybe_coast)
        self.unit = unit
        self.destination = destination_coast
    def __str__(self):
        return '%s %s - %s' % (self.unit.coast.unit_type,
                self.unit.coast.province, self.destination.maybe_coast)
    def order_note(self, power, phase, past_orders=None):
        note = self.__super.order_note(power, phase, past_orders)
        if note == MBV and self.destination.maybe_coast not in self.unit.retreats:
            note = NVR
        return note
    def create(klass, order, nation, board, datc):
        unit = board.ordered_unit(nation, order[0])
        dest = board.ordered_coast(unit, order[2], datc)
        result = klass(unit, dest)
        result.order = order
        return result
    create = classmethod(create)

class BuildPhaseOrder(UnitOrder):
    op = NotImplemented
    def required(self, power, past_orders):
        if past_orders: surplus = -past_orders.builds_remaining(power)
        else: surplus = power.surplus()
        return self.op(surplus, 0)
class WaiveOrder(BuildPhaseOrder):
    order_type = WVE
    op = lt
    def __init__(self, power):
        if power: self.key = (power.key, WVE)
        else: self.key = WVE
        self.nation = power
    def __str__(self):
        if self.nation: return '%s WVE' % (self.nation,)
        else: return 'WVE'
    def order_note(self, power, phase, past_orders=None):
        note = MBV
        if not (self.order_type.value() & phase):   note = NRS
        elif self.nation != power:                  note = NYU
        elif not self.required(power, past_orders): note = NMB
        return note
    def create(klass, order, nation, board, datc):
        for token in Message(order):
            if token.is_power():
                power = board.powers.get(token) or Power(token, [])
                break
        else: power = board.powers[nation.key]
        result = klass(power)
        result.order = order
        return result
    create = classmethod(create)
class BuildOrder(BuildPhaseOrder):
    order_type = BLD
    op = lt
    def __init__(self, unit):
        self.key = (unit.key, BLD)
        self.unit = unit
        self.destination = unit.coast
    def order_note(self, power, phase, past_orders=None):
        note = self.__super.order_note(power, phase, past_orders)
        if note == NSU:
            coast = self.unit.coast
            old_order = past_orders and past_orders.has_order(coast.province)
            if not coast.exists():                                 note = CST
            elif not coast.province.is_supply():                   note = NSC
            elif self.unit.nation != coast.province.owner:         note = YSC
            elif self.unit.nation.key not in coast.province.homes: note = HSC
            elif coast.province.units:                             note = ESC
            elif old_order:                                        note = ESC
            elif not self.required(power, past_orders):            note = NMB
            else:                                                  note = MBV
        elif note == MBV:                                          note = ESC
        return note
class RemoveOrder(BuildPhaseOrder):
    order_type = REM
    op = gt
    def __init__(self, unit):
        self.key = (unit.key, REM)
        self.unit = unit
    def order_note(self, power, phase, past_orders=None):
        note = self.__super.order_note(power, phase, past_orders)
        if note == MBV and not self.required(power, past_orders): note = NMR
        return note

_class_types = {
    HLD: HoldOrder,
    MTO: MoveOrder,
    SUP: SupportOrder,
    CVY: ConvoyingOrder,
    CTO: ConvoyedOrder,
    RTO: RetreatOrder,
    DSB: DisbandOrder,
    BLD: BuildOrder,
    REM: RemoveOrder,
    WVE: WaiveOrder,
}
def UnitOrder(order, nation, board, datc):
    ''' Determine the class of the order, and create one of that type.
        This function hides the definition of the UnitOrder class,
        but is more useful.
        
        order is a folded message, part of a SUB command;
        nation is the country making the order;
        board is a Map object.
    '''#'''
    return _class_types[order[1]].create(order, nation, board, datc)

class OrderSet(dict):
    ''' A mapping of Coast key -> UnitOrder, with special provisions for Waives.
        Warning: This currently assumes a single unit per coast,
        and a single order per unit.
        
        >>> Moscow = standard_map.spaces[MOS].unit
        >>> Warsaw = standard_map.spaces[WAR].unit
        >>> Russia = standard_map.powers[RUS]
        >>> France = standard_map.powers[FRA]
        >>> russian = OrderSet(Russia)
        >>> russian.add(HoldOrder(Moscow))
        >>> russian.add(WaiveOrder(Russia))
        >>> russian.add(MoveOrder(Moscow, Warsaw))
        >>> russian.add(WaiveOrder(France))
        >>> print russian.create_SUB()
        SUB ( ( RUS AMY MOS ) MTO WAR ) ( RUS WVE ) ( FRA WVE )
    '''#'''
    def __init__(self, default_nation=None):
        self.default = default_nation
    def __getitem__(self, key):
        ''' Similar to DefaultDict, from Peter Norvig's IAQ.'''
        if key in self: return self.get(key)
        return self.setdefault(key, [])
    def __len__(self):
        ''' Primarily to allow "if order_set:" to work as expected,
            but also makes iteration slightly more efficient.
        '''#'''
        return sum([len(orders) for orders in self.itervalues()])
    def __iter__(self):
        ''' Allows the construction "for order in order_set:" '''
        from itertools import chain
        return chain(*self.values())
    def __str__(self):
        nations = DefaultDict([])
        for order in self:
            key = order.__author and order.__author.key
            nations[key].append(order)
        return '{ %s }' % '; '.join(['%s: %s' %
                (nation, ', '.join(map(str, orders)))
            for nation, orders in nations.iteritems()])
    def __copy__(self):
        # Inefficient, but it works much better than straight copy() does.
        result = OrderSet(self.default)
        for order in self:
            item = order.unit or order.nation
            result[item.key].append(order)
        return result
    
    def add(self, order, nation=None):
        order.__author = nation or self.default
        item = order.unit or order.nation
        self[item.key].append(order)
    def remove(self, order, nation=None):
        ''' Attempt to remove a specific order.
            Returns the actual order removed, or None if it wasn't found.
            
            >>> english = OrderSet(); print english
            { }
            >>> London = standard_map.spaces[LON].units[0]
            >>> NorthSea = standard_map.coasts[(FLT, NTH, None)]
            >>> EngChannel = standard_map.coasts[(FLT, ECH, None)]
            >>> english.add(ENG, MoveOrder(London, NorthSea)); print english
            { ENG: FLT LON - NTH }
            >>> english.add(ENG, MoveOrder(London, EngChannel)); print english
            { ENG: FLT LON - NTH, FLT LON - ECH }
            >>> english.remove(ENG, MoveOrder(London, NorthSea)); print english
            FLT LON - NTH
            { ENG: FLT LON - ECH }
            >>> english.remove(GER, MoveOrder(London, EngChannel)); print english
            { ENG: FLT LON - ECH }
        '''#'''
        author = nation or self.default
        order_list = self[(order.unit or order.nation).key]
        for index, item in enumerate(order_list):
            if item == order and (item.__author == author or not author):
                return order_list.pop(index)
        return None
    def waive(self, number, nation=None):
        for dummy in range(number):
            self.add(WaiveOrder(nation or self.default), nation)
    def create_SUB(self, nation=None):
        ''' Returns a Message for submitting these orders to the server,
            or None if no orders need to be sent.
            Use the nation argument to submit only that nation's orders.
        '''#'''
        result = self.order_list(nation)
        if result: return SUB(*result)
        return None
    def order_list(self, nation=None):
        if nation: return [o for o in sum(self.values(), []) if o.__author == nation]
        else:      return [o for o in sum(self.values(), [])]
    def clear(self, nation=None):
        if nation:
            for key, orders in self.items():
                self[key] = [o for o in orders if o.__author != nation]
        else: dict.clear(self)
    
    def holding(self): return [o for o in self if o.is_holding()]
    def moving_into(self, province):
        return [order for order in self if order.is_moving()
            and order.destination.province.key == province.key]
    def is_moving(self, unit):
        result = self.get_order(unit)
        return result and result.is_moving()
    def has_order(self, province):
        for order in self:
            if order.unit and order.unit.coast.province == province:
                return True
        else: return False
    def get_order(self, unit):
        ''' Find the "best" order for a given unit.
            Currently returns the last order given by the unit's owner.
        '''#'''
        result = None
        for order in self[unit.key]:
            if order.__author == unit.nation: result = order
        return result
    
    def builds_remaining(self, power):
        # Todo: Don't count duplicate REM orders
        surplus = power.surplus()
        for order in self.order_list(power):
            if surplus < 0 and order.order_type in (WVE, BLD): surplus += 1
            elif surplus > 0 and order.order_type == REM:      surplus -= 1
        return -surplus
    def missing_orders(self, phase, nation=None):
        ''' Returns the MIS message for the power,
            or None if no orders are required.
            Either nation or the default nation must be a Power object.
            
            # Basic check
            >>> empty_set = OrderSet()
            >>> italy = standard_map.powers[ITA]
            >>> print empty_set.missing_orders(italy, Turn.build_phase)
            None
            
            # Crazy setup:
            # Venice is already holding,
            # Rome is dislodged and must retreat to either Tuscany or Apulia,
            # and Tunis is vacant but controlled by Italy.
            >>> standard_map.coasts[(AMY, VEN, None)].set_hold_order()
            >>> rome = standard_map.coasts[(AMY, ROM, None)]
            >>> rome.dislodged = italy; rome.nation = None
            >>> rome.retreats = [APU, TUS]
            >>> italy.dislodged[rome.key] = rome
            >>> del italy.units[rome.key]
            >>> italy.centers.append(TUN)
            >>> turn = standard_map.current_turn
            
            # Test various phases
            >>> print empty_set.missing_orders(italy, Turn.move_phase)
            MIS ( ITA FLT NAP )
            >>> print empty_set.missing_orders(italy, Turn.retreat_phase)
            MIS ( ITA AMY ROM MRT ( APU TUS ) )
            >>> print empty_set.missing_orders(italy, Turn.build_phase)
            MIS ( -1 )
            
            # Restore original map
            >>> standard_map.restart()
        '''#'''
        power = nation or self.default
        if phase == Turn.move_phase:
            result = [unit for unit in power.units
                if not self.get_order(unit)]
            if result: return MIS(*result)
        elif phase == Turn.retreat_phase:
            result = [unit for unit in power.units
                if unit.dislodged and not self.get_order(unit)]
            if result: return MIS(*result)
        elif phase == Turn.build_phase:
            surplus = -self.builds_remaining(power)
            if surplus: return MIS(surplus)
        return None
    def complete_set(self, board):
        ''' Fills out the order set with default orders for the phase.
            Assumes that all orders in the set are valid.
        '''#'''
        phase = board.current_turn.phase()
        if phase == Turn.move_phase:
            self.default_orders(HoldOrder, board)
        elif phase == Turn.retreat_phase:
            self.default_orders(DisbandOrder, board)
        elif phase == Turn.build_phase:
            for power in board.powers.itervalues():
                builds = self.builds_remaining(power)
                if builds > 0:   self.waive(power, builds)
                elif builds < 0: self.default_removes(-builds, power, board)
        else: raise UserWarning, 'Unknown phase %d' % phase
    def default_removes(self, surplus, power, board):
        units = power.farthest_units(board.distance)
        while surplus > 0 and units:
            unit = units.pop(0)
            if not self.has_key(unit.coast.key):
                self.add(RemoveOrder(unit), power)
                surplus -= 1
    def default_orders(self, order_class, board):
        for unit in board.units:
            if not self.get_order(unit):
                self.add(order_class(unit), unit.nation)


def _test():
    ''' Exercises the doctests above.
        For convenience and time, standard_map and its tokens
        are added to the global dictionary.
    '''#'''
    import doctest, orders
    globs = config.extend_globals(orders.__dict__)
    return doctest.testmod(orders, globs=globs)
if __name__ == "__main__": _test()

# vim: sts=4 sw=4 et tw=75 fo=crql1
