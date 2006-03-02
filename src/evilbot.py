''' EvilBot - A cheating diplomacy bot that plays multiple positions
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
'''#'''

from thread       import allocate_lock
from operator     import add
from sets         import Set
from orders       import OrderSet
from functions    import version_string
from dumbbot      import DumbBot

__version__ = "$Revision$"

class EvilBot(DumbBot):
    ''' Based on the DumbBot algorithm, but allies with other instances.
        Only instances created in the same program are recognized.
    '''#'''
    
    # Items for the NME message
    name    = 'EvilBot'
    version = version_string(__version__)
    description = 'A cheating scumball'
    
    # Static variables
    main_lock = allocate_lock()
    print_csv = False
    games = {}
    
    class shared_info(object):
        def __init__(self):
            self.lock = allocate_lock()
            self.friends = Set()
            self.laughs = 3
            self.orders = None
            self.turn = None
    
    def __init__(self, *args, **kwargs):
        self.__super.__init__(*args, **kwargs)
        self.game_id = game = kwargs.get('game_id')
        try:
            self.log_debug(11, 'Acquiring init lock')
            self.main_lock.acquire()
            if self.games.has_key(game): shared = self.games[game]
            else: self.games[game] = shared = self.shared_info()
        finally:
            self.log_debug(11, 'Releasing init lock')
            self.main_lock.release()
        self.shared = shared
        if self.power: shared.friends.add(self.power.key)
    def handle_HLO(self, message):
        print 'EvilBot takes over %s, passcode %d!' % (message[2], message[5].value())
        self.shared.friends.add(message[2])
        super(EvilBot, self).handle_HLO(message)
    
    def friendly(self, nation): return nation.key in self.shared.friends
    def generate_movement_orders(self, values):
        ''' Generate the actual orders for a movement turn.'''
        now = self.map.current_turn
        self.log_debug(10, "Movement orders for %s" % now)
        lock = self.shared.lock
        try:
            self.log_debug(11, 'Acquiring movement lock')
            lock.acquire()
            turn = self.shared.turn
            self.log_debug(11, 'Comparing %s with %s', turn, now)
            if turn and turn == now.key:
                self.log_debug(11, 'Using stored orders')
                orders = self.shared.orders
            else:
                self.log_debug(11, 'Calculating new orders')
                orders = self.dumb_movement(values, OrderSet(),
                        [u for u in self.map.units if self.friendly(u.nation)])
                self.check_for_wasted_holds(orders, values)
                self.shared.orders = orders
                self.shared.turn = now.key
        finally:
            self.log_debug(11, 'Releasing movement lock')
            lock.release()
        return orders
    
    def handle_SCO(self, message):
        ''' Flags self-copies as friends, before setting power sizes,
            and sets appropriate draw settings.
        '''#'''
        for ally in self.shared.friends:
            if self.map.powers[ally].units: self.attitude[ally] = -.1
            else: self.attitude[ally] = 2
        self.draws = [self.shared.friends & Set(self.map.current_powers())]
        super(EvilBot, self).handle_SCO(message)
    def handle_DRW(self, message):
        '''Laugh at the poor humans.'''
        lock = self.shared.lock
        try:
            self.log_debug(11, 'Acquiring draw lock')
            lock.acquire()
            if self.power.units:
                self.send_admin('Bwa' + '-ha' * self.shared.laughs + '!')
            self.shared.laughs += 1
        finally:
            self.log_debug(11, 'Releasing draw lock')
            lock.release()
        self.__super.handle_DRW(message)
    def handle_SLO(self, message):
        if message[2] == self.power:
            self.send_admin('You insignificant fools!')
            self.send_admin('Did you honestly think you could overcome the power of the dark side?')
        self.__super.handle_SLO(message)
    def handle_OFF(self, message):
        self.shared.friends.remove(self.power.key)
        self.__super.handle_OFF(message)


if __name__ == "__main__":
    import main
    main.run_player(EvilBot)
