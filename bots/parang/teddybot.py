r'''TeddyBot - A Diplomacy bot that attempts to choose targets.
    Copyright (C) 2008  Eric Wald
    
    This software may be reused for non-commercial purposes without charge,
    and without notifying the authors.  Use of any part of this software for
    commercial purposes without permission from the authors is prohibited.
'''#"""#'''

from parlance.functions import Infinity, cache, defaultdict
from parlance.orders import OrderSet, MoveOrder
from parlance.player import Player

class TeddyBot(Player):
    r'''A bot that attempts to choose targets carefully.
    '''#"""#'''
    
    def generate_orders(self):
        orders = OrderSet(self.power)
        turn = self.map.current_turn
        phase = turn.phase()
        if phase == turn.move_phase:
            for unit in self.power.units:
                for site in unit.coast.borders_out:
                    if not self.map.spaces[site[1]].units:
                        order = MoveOrder(unit, self.map.coasts[site])
                        orders.add(order, unit.nation)
        
        orders.complete_set(self.map)
        self.submit_set(orders)
    
    def process_map(self):
        r'''Performs supplemental processing on the map.
            For TeddyBot, this involves distance and centrality calculations.
            Returns whether to accept the MAP message.
        '''#"""#'''
        self.distance = cache('Teddy.distance.' + self.map.name,
            self.calc_distances)
        self.centrality = cache('Teddy.centrality.' + self.map.name,
            self.calc_centrality, self.distance)
        return True
    
    def calc_distances(self):
        distance = defaultdict(lambda: Infinity)
        
        coasts = self.map.coasts
        for source in coasts:
            distance[source, source] = 0
            for border in coasts[source].borders_out:
                distance[(source, border)] = 1
        for mid in coasts:
            for source in coasts:
                for sink in coasts:
                    dist = distance[(source, mid)] + distance[(mid, sink)]
                    if dist < distance[(source, sink)]:
                        distance[(source, sink)] = dist
        
        spaces = self.map.spaces
        for source in spaces:
            distance[source, source] = 0
            for border in spaces[source].borders_out:
                distance[(source, border)] = 1
        for mid in spaces:
            for source in spaces:
                for sink in spaces:
                    dist = distance[(source, mid)] + distance[(mid, sink)]
                    if dist < distance[(source, sink)]:
                        distance[(source, sink)] = dist
        
        return dict(distance)
    
    def calc_centrality(self, distance):
        closeness = {}
        coasts = self.map.coasts
        for source in coasts:
            closeness[source] = sum(2 ** -distance[source, sink]
                for sink in coasts if sink != source)
        spaces = self.map.spaces
        for source in spaces:
            closeness[source] = sum(2 ** -distance[source, sink]
                for sink in spaces if sink.is_supply())
        return closeness


def run():
    from parlance.main import run_player
    run_player(TeddyBot)
