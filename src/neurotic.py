''' Neurotic - A bot that tries to mimic its opponents.
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
'''#'''

from math         import sqrt
from time         import ctime

from bpnn         import NN
from config       import VerboseObject
from gameboard    import Unit
from orders       import *
from player       import Player
from tokens       import MBV

class Brain(VerboseObject):
    ''' Stores the neural networks for Neurotic bots.
        Designed to only require one Brain instance per map,
        without letting bots step on each others' toes.
    '''#'''
    
    def __init__(self, board):
        self.__super.__init__()
        # Inputs: Seasons, Coasts*Players, Centers*Players
        # Outputs: Provinces*(Provinces+Self+Adjacents+Coastals)
        # Consider: Player*(Player-1)
        
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
    
    def collect_values(self, board):
        turn = board.current_turn
        inputs = self.collect_inputs(board)
        self.log_debug(11, 'Inputs: %s', inputs)
        outputs = self.net.update(inputs)
        self.log_debug(11, 'Outputs: %s', outputs)
        return self.parse_outputs(board, outputs)
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
            unit = board.spaces[token].unit
            if unit:
                starting = dict()
                for prov in self.provinces:
                    if prov == token:
                        unit_value = outputs[index]
                        oclass = unit.dislodged and DisbandOrder or RemoveOrder
                        order_values.append((unit_value, oclass(unit)))
                    elif board.spaces[prov].unit:
                        starting[prov] = outputs[index]
                    index += 1
                
                for coast in self.coastlines[token]:
                    if coast == unit.coast.key:
                        hold_value = unit_value + outputs[index]
                        order_values.append((hold_value, HoldOrder(unit)))
                    index += 1
                
                for prov in self.borders[token]:
                    for key in self.coastlines[prov]:
                        dest = board.coasts[key]
                        if unit.can_move_to(dest):
                            value = unit_value + outputs[index]
                            oclass = unit.dislodged and RetreatOrder or MoveOrder
                            order_values.append((value, oclass(unit, dest)))
                        for start, start_value in starting.iteritems():
                            mover = board.spaces[start].unit
                            if mover.can_move_to(dest):
                                value = start_value + outputs[index]
                                order = SupportMoveOrder(unit, mover, dest)
                                order_values.append((value, order))
                        index += 1
                
                for key in self.coastals:
                    dest = board.coasts[key]
                    if unit.can_be_convoyed():
                        value = unit_value + outputs[index]
                        order = ConvoyedOrder(unit, dest)
                        order_values.append((value, order))
                    elif unit.can_convoy():
                        for start, start_value in starting.iteritems():
                            mover = board.spaces[start].unit
                            if mover.can_be_convoyed():
                                value = start_value + outputs[index]
                                order = SupportMoveOrder(unit, mover, dest)
                                order_values.append((value, order))
                    index += 1
            else:
                index += len(self.provinces)
                space = board.spaces[token]
                for key in self.coastlines[token]:
                    if space.homes:
                        coast = board.coasts[key]
                        value = outputs[index]
                        order_values.extend((value,
                                    BuildOrder(Unit(nation, coast)))
                                for nation in space.homes)
                    index += 1
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
    
    def load_weights(self, map_name):
        pass
    def store_weights(self, map_name):
        ''' Stores the weights used for the map.'''
        filename = 'log/bots/neurotic_%s.csv' % (map_name,)
        try: fp = open(filename, 'w')
        except IOError: self.log_debug(1, "Couldn't open csv file " + filename)
        else:
            try:
                fp.write(self.input_headers)
                fp.write(self.self.net.wi)
                fp.write(self.output_headers)
                fp.write(self.self.net.wo)
            finally:
                fp.close()

class Neurotic(Player):
    ''' A bot that tries to mimic its opponents.
        Yes, this uses a neural network.
    '''#'''
    
    def __init__(self, **kwargs):
        self.__super.__init__(**kwargs)
        self.log_debug(9, '%s (%s); started at %s',
                self.name, self.version, ctime())
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
            phase = self.phase()
            self.log_debug(10, 'Starting NOW %s message', self.map.current_turn)
            orders = self.orders
            missing = orders.missing_orders(phase)
            values = self.brain.collect_values(self.map)
            values.sort()
            
            while missing and values:
                value, order = values.pop()
                self.log_debug(11, 'Considering %s, worth %s', order, value)
                note = order.order_note(self.power, phase, orders)
                province = order.unit.coast.province
                if order.unit and orders.has_order(province):
                    self.log_debug(11, 'Already has an order for %s', province)
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


if __name__ == "__main__":
    from main import run_player
    run_player(Neurotic)
