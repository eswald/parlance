r'''TeddyBot - A Diplomacy bot that attempts to choose targets.
    Copyright (C) 2008  Eric Wald
    
    This software may be reused for non-commercial purposes without charge,
    and without notifying the authors.  Use of any part of this software for
    commercial purposes without permission from the authors is prohibited.
'''#"""#'''

from parlance.functions import Infinity, cache
from parlance.gameboard import Unit
from parlance.orders import OrderSet, BuildOrder, MoveOrder
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
                values = {}
                self.log_debug(9, unit)
                for site in unit.coast.borders_out:
                    space = self.map.spaces[site[1]]
                    supply = 0
                    if space.is_supply():
                        if space.owner != self.power:
                            supply = len(space.owner.centers)
                    value = (supply, self.centrality[site])
                    values[value] = site
                    self.log_debug(9, '%s: %s', site, value)
                destination = self.map.coasts[values[max(values)]]
                order = MoveOrder(unit, destination)
                orders.add(order, unit.nation)
        elif phase == turn.build_phase:
            builds = -self.power.surplus()
            if builds > 0:
                values = []
                for prov in self.power.homes:
                    space = self.map.spaces[prov]
                    if not space.units:
                        for site in space.coasts:
                            val = self.centrality[site.key]
                            values.append((val, site))
                for value, site in sorted(values)[-builds:]:
                    unit = Unit(self.power, site)
                    order = BuildOrder(unit)
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
        distance = {}
        
        coasts = self.map.coasts
        for source in coasts:
            for sink in coasts:
                distance[(source, sink)] = Infinity
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
            for sink in spaces:
                distance[(source, sink)] = Infinity
            distance[source, source] = 0
            for border in spaces[source].borders_out:
                distance[(source, border)] = 1
        for mid in spaces:
            for source in spaces:
                for sink in spaces:
                    dist = distance[(source, mid)] + distance[(mid, sink)]
                    if dist < distance[(source, sink)]:
                        distance[(source, sink)] = dist
        
        return distance
    
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
