''' Neurotic - A bot that tries to mimic its opponents.
    Copyright (C) 2007-2008  Eric Wald
    
    This software may be reused for non-commercial purposes without charge,
    and without notifying the authors.  Use of any part of this software for
    commercial purposes without permission from the authors is prohibited.
'''#'''

from cPickle import Pickler, Unpickler
from math    import sqrt
from time    import ctime

from parlance.config    import VerboseObject
from parlance.functions import defaultdict
from parlance.gameboard import Turn, Unit
from parlance.judge     import DatcOptions
from parlance.orders    import *
from parlance.player    import Player
from parlance.tokens    import MBV

from bpnn import NN

class Brain(VerboseObject):
    ''' Stores the neural networks for Neurotic bots.
        Designed to potentially require only one Brain instance per map,
        without letting bots step on each others' toes.
    '''#'''
    
    def __init__(self, board):
        self.__super.__init__()
        self.filename = 'log/bots/neurotic_%s.pkl' % (board.name,)
        self.sort_lists(board)
        if not self.load_weights(): self.create_net(board)
    def sort_lists(self, board):
        # Originally only in create_net()
        # All this sorting is probably unnecessary, but maintains consistency.
        self.seasons = board.current_turn.seasons[:]
        self.powers = sorted(board.powers.iterkeys())
        self.coasts = sorted(board.coasts.iterkeys())
        self.provinces = sorted(board.spaces.iterkeys())
        self.centers = [token for token in self.provinces if token.is_supply()]
        self.coastals = [board.spaces[token].is_coastal()
                for token in self.provinces if token.is_coastal()]
        self.coastlines = dict((token,
                    [coast.key for coast in sorted(province.coasts)])
                for token, province in board.spaces.iteritems())
        self.borders = dict((token, sorted(province.borders_out))
                for token, province in board.spaces.iteritems())
    def create_net(self, board):
        # Inputs: Seasons, Coasts*Players, Centers*Players
        # Outputs: Provinces*(Provinces+Self+Adjacents+Coastals)
        # Consider: Player*(Player-1)
        
        self.input_headers = map(str, self.seasons)
        for coast in self.coasts:
            if coast[2]:
                self.input_headers.extend(
                        "%s %s %s: %s" % (coast[0], coast[1], coast[2], power)
                        for power in self.powers)
            else:
                self.input_headers.extend(
                        "%s %s: %s" % (coast[0], coast[1], power)
                        for power in self.powers)
        for center in self.centers:
            self.input_headers.extend("%s: %s" % (center, power)
                    for power in self.powers)
        
        def dest(key):
            result = "%s %s" % (key[0], key[1])
            if key[2]: result += " " + str(key[2])
            return result
        self.output_headers = []
        for token in self.provinces:
            self.output_headers.extend("%s: From %s" % (token, prov)
                    for prov in self.provinces)
            self.output_headers.extend("%s: To %s" % (token, dest(coast))
                    for coast in self.coastlines[token])
            self.output_headers.extend("%s: To %s" % (token, dest(coast))
                    for prov in self.borders[token]
                    for coast in self.coastlines[prov])
            self.output_headers.extend("%s: CTO %s" % (token, dest(coast))
                    for coast in self.coastals)
        
        ni = len(self.input_headers)
        no = len(self.output_headers)
        nh = int(round(sqrt(ni * no)))
        self.log_debug(15, 'Inputs: %s', self.input_headers)
        self.log_debug(15, 'Outputs: %s', self.output_headers)
        self.log_debug(7, "%d inputs => %d hidden => %d outputs", ni, nh, no)
        self.net = NN(ni, nh, no)
    
    def collect_values(self, inputs, board):
        turn = board.current_turn
        self.log_debug(11, 'Inputs: %s', inputs)
        outputs = self.net.update(inputs)
        self.log_debug(11, 'Outputs: %s', outputs)
        orders = self.parse_outputs(board, outputs)
        return orders
    def collect_inputs(self, board):
        ''' Converts a board state into a list of inputs for the neural net.'''
        inputs = [0] * len(self.input_headers)
        inputs[board.current_turn.index] = 1
        index = len(self.seasons)
        for coast in self.coasts:
            units = board.coasts[coast].province.units
            for power in self.powers:
                inputs[index] = len([unit for unit in units
                            if unit.coast.key == coast
                            and unit.nation == power])
                index += 1
        for center in self.centers:
            owner = board.spaces[center].owner
            for power in self.powers:
                inputs[index] = int(owner == power)
                index += 1
        return inputs
    def parse_outputs(self, board, outputs):
        ''' Converts a neural net output list into potential orders.'''
        order_values = []
        index = 0
        for token in self.provinces:
            units = board.spaces[token].units
            if units:
                starting = dict()
                for prov in self.provinces:
                    if prov == token:
                        unit_value = outputs[index]
                        order_values.extend((unit_value, (unit.dislodged
                                    and DisbandOrder or RemoveOrder)(unit))
                            for unit in units)
                    elif board.spaces[prov].units:
                        starting[prov] = outputs[index]
                    index += 1
                
                for coast in self.coastlines[token]:
                    hold_value = unit_value + outputs[index]
                    order_values.extend((hold_value, HoldOrder(unit))
                        for unit in units if coast == unit.coast.key)
                    index += 1
                
                for prov in self.borders[token]:
                    for key in self.coastlines[prov]:
                        dest = board.coasts[key]
                        value = unit_value + outputs[index]
                        order_values.extend((value, (unit.dislodged
                                    and RetreatOrder or MoveOrder)(unit, dest))
                            for unit in units if unit.can_move_to(dest))
                        for start, start_value in starting.iteritems():
                            for mover in board.spaces[start].units:
                                if mover.can_move_to(dest):
                                    value = start_value + outputs[index]
                                    order_values.extend((value,
                                                SupportMoveOrder(unit,
                                                    mover, dest))
                                            for unit in units)
                        index += 1
                
                for key in self.coastals:
                    dest = board.coasts[key]
                    for unit in units:
                        if unit.can_be_convoyed():
                            order_values.append((unit_value + outputs[index],
                                        ConvoyedOrder(unit, dest)))
                        elif unit.can_convoy():
                            for start, start_value in starting.iteritems():
                                for mover in board.spaces[start].units:
                                    if mover.can_be_convoyed():
                                        value = start_value + outputs[index]
                                        order_values.append((value,
                                                    ConvoyingOrder(unit,
                                                        mover, dest)))
                    index += 1
            else:
                index += len(self.provinces)
                space = board.spaces[token]
                if space.owner:
                    for key in self.coastlines[token]:
                        coast = board.coasts[key]
                        value = outputs[index]
                        order_values.append((value,
                                    BuildOrder(Unit(space.owner, coast))))
                    index += 1
                else: index += len(self.coastlines[token])
                index += sum(len(self.coastlines[prov])
                        for prov in self.borders[token])
                index += len(self.coastals)
        for nation in board.powers.itervalues():
            waives = -nation.surplus()
            while waives > 0:
                order_values.append((0.5, WaiveOrder(nation)))
                waives -= 1
        self.log_debug(7, "Outputs: %d; Index: %d; Orders: %d",
                len(outputs), index, len(order_values))
        for value, order in order_values:
            self.log_debug(15, "%s: %s", value, order)
        return order_values
    
    def learn(self, inputs, orders, board):
        ''' Trains the neural net to produce the given orders.'''
        outputs = self.parse_orders(orders, board)
        ins = [x for i, x in enumerate(self.input_headers) if inputs[i]]
        outs = [x for i, x in enumerate(self.output_headers) if outputs[i]]
        self.log_debug(1, 'Training %s to produce %s.', ins, outs)
        self.net.learn(inputs, outputs, iterations=1)
    def parse_orders(self, orders, board):
        ''' Converts an order set into a neural net output list.'''
        outputs = [0] * len(self.output_headers)
        index = 0
        prov_orders = {}
        for order in orders:
            if order.unit:
                prov_orders[order.unit.coast.province.key] = order
        for token in self.provinces:
            if prov_orders.has_key(token):
                order = prov_orders[token]
                for prov in self.provinces:
                    if prov == token:
                        if isinstance(order, (DisbandOrder, RemoveOrder,
                                    HoldOrder, RetreatOrder, MoveOrder)):
                            outputs[index] = 1
                    elif board.spaces[prov].unit:
                        if (isinstance(order, (SupportOrder, ConvoyingOrder))
                                and order.supported.coast.province == token):
                            outputs[index] = 1
                    index += 1
                
                for coast in self.coastlines[token]:
                    if (isinstance(order, HoldOrder)
                            and coast == order.unit.coast.key):
                        outputs[index] = 1
                    index += 1
                
                for prov in self.borders[token]:
                    for key in self.coastlines[prov]:
                        if (isinstance(order, (RetreatOrder,
                                        MoveOrder, SupportMoveOrder))
                                and order.destination.key == key):
                            outputs[index] = 1
                        index += 1
                
                for key in self.coastals:
                    if (isinstance(order, (ConvoyedOrder, ConvoyingOrder))
                            and order.destination.key == key):
                        outputs[index] = 1
                    index += 1
            else:
                index += len(self.provinces)
                index += len(self.coastlines[token])
                index += sum(len(self.coastlines[prov])
                        for prov in self.borders[token])
                index += len(self.coastals)
        return outputs
    
    def load_weights(self):
        ''' Loads the stored data from previous sessions, if possible.'''
        valid = False
        try: fp = open(self.filename, 'r')
        except IOError:
            self.log_debug(11, "Couldn't read stats file '%s'", self.filename)
        else:
            self.log_debug(11, "Loading stats file '%s'", self.filename)
            try:
                pickler = Unpickler(fp)
                self.input_headers = pickler.load()
                wi = pickler.load()
                self.output_headers = pickler.load()
                wo = pickler.load()
                #self.seasons = pickler.load()
                #self.powers = pickler.load()
                #self.coasts = pickler.load()
                #self.provinces = pickler.load()
                #self.centers = pickler.load()
                #self.coastals = pickler.load()
                #self.coastlines = pickler.load()
                #self.borders = pickler.load()
            finally:
                fp.close()
            
            ni = len(self.input_headers)
            no = len(self.output_headers)
            nh = len(wo)
            self.log_debug(7, "%d inputs => %d hidden => %d outputs",
                    ni, nh, no)
            self.net = NN(ni, nh, no, wi, wo)
            valid = True
        return valid
    def store_weights(self):
        ''' Stores the weights used for the map.'''
        try: fp = open(self.filename, 'w')
        except IOError:
            self.log_debug(1, "Couldn't write stats file '%s'", self.filename)
        else:
            self.log_debug(11, "Writing stats file '%s'", self.filename)
            try:
                pickler = Pickler(fp, -1)
                pickler.dump(self.input_headers)
                pickler.dump(self.net.wi)
                pickler.dump(self.output_headers)
                pickler.dump(self.net.wo)
                #pickler.dump(self.seasons)
                #pickler.dump(self.powers)
                #pickler.dump(self.coasts)
                #pickler.dump(self.provinces)
                #pickler.dump(self.centers)
                #pickler.dump(self.coastals)
                #pickler.dump(self.coastlines)
                #pickler.dump(self.borders)
            finally:
                fp.close()
    def close(self):
        ''' Called whenever a Neurotic closes.'''
        self.store_weights()

class Neurotic(Player):
    ''' A bot that tries to mimic its opponents.
        Yes, this uses a neural network.
    '''#'''
    
    def __init__(self, **kwargs):
        self.brain = None
        self.__super.__init__(**kwargs)
        self.log_debug(9, '%s (%s); started at %s',
                self.name, self.version, ctime())
        self.inputs = {}
        self.learned = defaultdict(OrderSet)
        self.last_turn = None
        self.datc = DatcOptions()
    def process_map(self):
        self.brain = Brain(self.map)
        return True
    def generate_orders(self):
        ''' Create and send orders for the phase.
            Warning: This function is executed in a separate thread.
            This means that it won't kill the whole bot on errors,
            but it might get called again before completing.
        '''#'''
        try:
            turn = self.map.current_turn
            phase = turn.phase()
            self.log_debug(10, 'Starting NOW %s message', turn)
            orders = self.orders
            missing = orders.missing_orders(phase)
            values = self.brain.collect_values(self.inputs[turn.key], self.map)
            values.sort()
            
            while missing and values:
                value, order = values.pop()
                self.log_debug(11, 'Considering %s, worth %s', order, value)
                note = order.order_note(self.power, phase, orders)
                if order.unit and orders.has_order(order.unit.coast.province):
                    self.log_debug(11, 'Already has an order for %s',
                            order.unit.coast.province)
                    continue
                elif note != MBV:
                    self.log_debug(11, 'Bad order: %s', note)
                    continue
                else:
                    self.log_debug(9, 'Ordering %s, worth %s', order, value)
                    orders.add(order)
                    missing = orders.missing_orders(phase)
            
            if missing:
                self.log_debug(7, 'Still missing orders: %s', missing)
                orders.complete_set(self.map)
            if orders: self.submit_set(orders)
        except:
            self.log_debug(1, 'Error while handling NOW %s message', turn)
            self.close()
            raise
    def close(self):
        if self.brain: self.brain.close()
        self.__super.close()
    
    def handle_ORD(self, message):
        msg = message.fold()
        turn = Turn(*msg[1])
        if turn != self.map.current_turn:
            self.log_debug(1, 'Order for %s in %s',
                    turn, self.map.current_turn)
        order = createUnitOrder(msg[2], None, self.map, self.datc)
        nation = (order.unit or order).nation
        self.log_debug(11, '(%s) %s %s', turn, nation, order)
        self.learned[turn.key].add(order)
        self.last_turn = turn.key
    def handle_NOW(self, message):
        ''' Overrides Player.handle_NOW to ensure that inputs are calculated,
            and to train the brain with any moves recently learned.
        '''#'''
        last_turn = self.last_turn
        self.last_turn = None
        
        turn = self.map.current_turn
        self.inputs[turn.key] = self.brain.collect_inputs(self.map)
        self.__super.handle_NOW(message)
        
        if last_turn:
            self.brain.learn(self.inputs[last_turn],
                    self.learned[last_turn], self.map)
            del self.inputs[last_turn]
            del self.learned[last_turn]


def run():
    from main import run_player
    run_player(Neurotic)
