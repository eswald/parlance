''' PeaceBot - An overly trusting diplomacy bot.
    Copyright (C) 2006 Eric Wald
    Licensed under the Open Software License version 3.0
'''#'''

from sets         import Set
from orders       import OrderSet
from functions    import version_string
from dumbbot      import DumbBot
from language     import *

__version__ = "$Revision$"

class PeaceBot(DumbBot):
    ''' Based on the DumbBot algorithm, but allies with other instances.
        Uses honest press messages to ally and coordinate moves.
    '''#'''
    
    # Items for the NME message
    name    = 'PeaceBot'
    version = version_string(__version__)
    description = 'An overly trusting bot that just wants peace'
    
    # Static variables
    print_csv = True
    
    def __init__(self, *args, **kwargs):
        self.__super.__init__(*args, **kwargs)
        self.friends = Set()
        self.draws = [self.friends]
        self.order_list = None
        #self.press_tokens = [ALY, BWX, DRW, PCE, PRP, REJ, VSS, XDO, YDO, YES]
        self.press_tokens = [PCE, PRP, YES]
    def handle_HLO(self, message):
        self.__super.handle_HLO(message)
        me = message[2]
        if me.is_power():
            self.friends.add(me)
            self.countries = Set(self.map.powers.keys())
            if self.opts.LVL >= 10:
                for country in self.countries:
                    if country is not me:
                        self.send_press(country, PRP(PCE([country, me])))
                    self.attitude[country] = 3
        else: self.close()
    def handle_SCO(self, message):
        self.__super.handle_SCO(message)
        if self.power.centers:
            for country in list(self.friends):
                power = self.map.powers[country]
                if not power.centers:
                    self.friends.remove(country)
    
    def friendly(self, nation): return nation.key in self.friends
    def generate_movement_orders(self, values):
        ''' Generate the actual orders for a movement turn.'''
        now = self.map.current_turn
        self.log_debug(10, "Movement orders for %s" % now)
        orders = self.dumb_movement(values, OrderSet(), self.power.units)
        self.check_for_wasted_holds(orders, values)
        #if self.submitted: orders = None
        #else: self.send(NOT(GOF))
        return orders
    def generate_allied_orders(self, values):
        orders = self.dumb_movement(values, OrderSet(),
                [u for u in self.map.units if self.friendly(u.nation)])
        self.check_for_wasted_holds(orders, values)
        return orders
    
    # Press handling routines
    def handle_press_PRP(self, sender, message):
        self.log_debug(1, 'Handling PRP press from %s: "%s".', sender, message)
        if message[1][0] is PCE:
            self.send_press(sender, YES(message))
            self.friends.add(sender)
            self.attitude[sender] -= 2
            self.log_debug(1, "Setting attitude toward %s to %d.",
                    sender, self.attitude[sender])
        # ALY, DRW, PCE, XDO, YDO
    def handle_press_YES(self, sender, message):
        self.log_debug(1, 'Handling YES press from %s: "%s".', sender, message)
        if message[1][0] is PRP and message[1][1][0] is PCE:
            self.friends.add(sender)
            self.attitude[sender] -= 2
            self.log_debug(1, "Setting attitude toward %s to %d.",
                    sender, self.attitude[sender])
    def handle_press_REJ(self, sender, message):
        self.log_debug(1, 'Handling press from %s: "%s".', sender, message)
        if message[1][0] is PRP and message[1][1][0] is PCE:
            self.attitude[sender] += 25
            self.log_debug(1, "Setting attitude toward %s to %d.",
                    sender, self.attitude[sender])
    handle_press_BWX = handle_press_REJ
    def handle_press_HUH(self, sender, message):
        flattened = Message(message)
        while ERR in flattened: flattened.pop(flattened.index(ERR))
        folded = flattened.fold()
        self.handle_press_REJ(sender, folded)


if __name__ == "__main__":
    import main
    main.run_player(PeaceBot)
