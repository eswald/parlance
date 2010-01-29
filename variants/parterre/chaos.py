r'''Chaos-specific Parlance Judge
    Copyright (C) 2009  Eric Wald
    
    This judge overrides the default remove order (for use when a player
    fails to submit orders) to be based on distance from currently owned
    supply centers, instead of home centers.
    
    This software may be reused for non-commercial purposes without charge,
    and without notifying the authors.  Use of any part of this software for
    commercial purposes without permission from the authors is prohibited.
'''#'''

from parlance.judge import Judge

class ChaosJudge(Judge):
    def farthest_units(self, power):
        distance = self.map.distance
        dist_list = [(
            -distance(unit.location, power.centers),    # Farthest unit
            -unit.location.unit_type.number,            # Fleets before armies
            unit.location.province.key.text,            # First alphabetically
            unit
        ) for unit in power.units]
        
        dist_list.sort()
        self.log.debug("Using Chaos rules for automatic removal among %r",
            dist_list)
        return [item[3] for item in dist_list]
