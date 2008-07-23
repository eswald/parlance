r'''TeddyBot - A Diplomacy bot that attempts to choose targets.
    Copyright (C) 2008  Eric Wald
    
    This software may be reused for non-commercial purposes without charge,
    and without notifying the authors.  Use of any part of this software for
    commercial purposes without permission from the authors is prohibited.
'''#"""#'''

from parlance.player import Player
from parlance.orders import OrderSet

class TeddyBot(Player):
    r'''A bot that attempts to choose targets carefully.
    '''#"""#'''
    
    def generate_orders(self):
        orders = OrderSet(self.power)
        orders.complete_set(self.map)
        self.submit_set(orders)


def run():
    from parlance.main import run_player
    run_player(TeddyBot)
