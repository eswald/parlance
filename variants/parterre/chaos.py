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
        def distance(location, homes):
            # Ignore the list of homes.
            return self.map.distance(location, power.centers)
        return power.farthest_units(distance)
