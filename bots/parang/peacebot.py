''' PeaceBot - An overly trusting diplomacy bot.
    Copyright (C) 2006-2008  Eric Wald
    
    This software may be reused for non-commercial purposes without charge,
    and without notifying the authors.  Use of any part of this software for
    commercial purposes without permission from the authors is prohibited.
'''#'''

from parang.dumbbot    import DumbBot
from parlance.language import Message
from parlance.orders   import OrderSet
from parlance.tokens   import ERR, PCE, PRP, YES

class PeaceBot(DumbBot):
    ''' An overly trusting bot that just wants peace.
        Based on the DumbBot algorithm, but allies with other instances.
        Uses honest press messages to ally and coordinate moves.
    '''#'''
    
    def __init__(self, **kwargs):
        self.__super.__init__(**kwargs)
        self.friends = set()
        self.draws = [self.friends]
        self.order_list = None
        #self.press_tokens = [ALY, BWX, DRW, PCE, PRP, REJ, VSS, XDO, YDO, YES]
        self.press_tokens = [PCE, PRP, YES]
    def handle_HLO(self, message):
        self.__super.handle_HLO(message)
        me = message[2]
        if me.is_power():
            self.friends.add(me)
            self.countries = set(self.map.powers.keys())
            if self.game_opts.LVL >= 10:
                for country in self.countries:
                    if country is not me:
                        self.send_press(country, PRP(PCE(country, me)))
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


def run():
    from parlance.main import run_player
    run_player(PeaceBot)
