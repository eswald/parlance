''' DAIDE Gameboard Classes
    Defines classes to represent parts of the Diplomacy game.
'''#'''

import config
from sets        import Set
from itertools   import chain
from functions   import Verbose_Object, Comparable, any, all
from iaq         import DefaultDict #, Memoize
from language    import Token, Message, AMY, FLT, MRT, NOW, SCO, UNO

def location_key(unit_type, loc):
    if isinstance(loc, Token): return (unit_type, loc,    None)
    else:                      return (unit_type, loc[0], loc[1])

class Map(Verbose_Object):
    ''' The map for the game, with various notes.
        Variables:
            - name:     The name used to request this map
            - valid:    Whether the map has been correctly loaded
            - powers:   A map of Powers in the game (Token -> Power)
            - spaces:   A map of Provinces (Token -> Province)
            - coasts:   A map of Coasts ((unit,province,coast) -> Coast)
            - neutral:  A Power representing the neutral supply centers
    '''#'''
    
    def __init__(self, options):
        ''' Initializes the map from an instance of config.variant_options.
        '''#'''
        self.powers  = []
        self.opts    = options
        self.name    = options.map_name
        self.valid   = options.map_mdf and not self.define(options.map_mdf)
        self.current_turn = Turn(options.seasons)
        self.restart()
    def __str__(self): return "Map(%r)" % self.name
    prefix = property(fget=__str__)
    
    def define(self, message):
        ''' Attempts to create a map from an MDF message.
            Returns True if successful, False otherwise.
            
            >>> mdf = MDF([ENG, FRA], ([
            ...     (ENG, EDI, LON),
            ...     (FRA, BRE, PAR), 
            ...     ([ENG, FRA], BEL, HOL), 
            ...     (UNO, SPA, NWY), 
            ... ], [ECH, NTH, PIC]), [
            ...     (EDI, [AMY, LON], [FLT, NTH]),
            ...     (LON, [AMY, EDI], [FLT, NTH, ECH]),
            ...     (BRE, [AMY, PAR, PIC, SPA], [FLT, ECH, PIC, (SPA, NCS)]),
            ...     (PAR, [AMY, PAR, SPA, PIC]),
            ...     (BEL, [AMY, PIC, HOL], [FLT, NTH, ECH, PIC, HOL]),
            ...     (HOL, [AMY, BEL], [FLT, NTH]),
            ...     (SPA, [AMY, PAR, BRE], [(FLT, NCS), BRE]),
            ...     (NWY, [AMY], [FLT, NTH]),
            ...     (ECH, [FLT, NTH, BRE, LON, BEL, PIC]),
            ...     (NTH, [FLT, ECH, BEL, HOL, LON, NWY, EDI]),
            ...     (PIC, [AMY, BRE, PAR, BEL], [FLT, ECH, BRE, BEL]),
            ... ])
            >>> print mdf.validate(None, -1, True)
            False
            >>> m = Map('simplified', config.default_rep)
            >>> m.valid
            False
            >>> m.define(mdf)
            ''
        '''#'''
        (mdf, powers, provinces, adjacencies) = message.fold()
        (centres, non_centres) = provinces
        pow_homes = {}
        prov_homes = {}
        for dist in centres:
            pow_list = dist.pop(0)
            if pow_list == UNO:
                for prov in dist:
                    if prov_homes.has_key(prov):
                        return 'Supply center %s listed as both owned and unowned' % str(prov)
                    prov_homes[prov] = []
            else:
                if not isinstance(pow_list, list): pow_list = [pow_list]
                for country in pow_list:
                    pow_homes.setdefault(country, []).extend(dist)
                for prov in dist:
                    prov_homes.setdefault(prov, []).extend(pow_list)
        
        pows = {}
        for country, homes in pow_homes.iteritems():
            pows[country] = Power(country, homes)
        self.powers = pows
        self.neutral = Power(UNO, [])
        
        provs = {}
        coasts = {}
        for adj in adjacencies:
            prov = adj.pop(0)
            is_sc = prov_homes.has_key(prov)
            non_sc = prov in non_centres
            if is_sc == non_sc:
                return 'Conflicting supply center designation for ' + str(prov)
            elif is_sc: home = prov_homes[prov]
            else:       home = None
            
            province = Province(prov, adj, home)
            provs[prov] = province
            for coast in province.coasts: coasts[coast.key] = coast
        for key,coast in coasts.iteritems():
            for other in coast.borders_out:
                coasts[other].borders_in.add(key)
                provs[other[1]].borders_in.add(key[1])
        self.spaces = provs
        self.coasts = coasts
        
        self.read_names()
        for prov in provs.itervalues():
            if not prov.is_valid(): return 'Invalid province: ' + str(prov)
        else: return ''
    def read_names(self):
        ''' Attempts to read the country and province names from a file.
            No big deal if it fails, but it's a nice touch.
        '''#'''
        try: name_file = self.opts.open_file('nam')
        except: return
        try:
            for line in name_file:
                fields = line.strip().split(':')
                if fields[0]:
                    token = Token(fields[0].upper(), rep=self.opts.rep)
                    if token.is_power():
                        self.powers[token].name = fields[1]
                        self.powers[token].adjective = fields[2]
                    elif token.is_province():
                        self.spaces[token].name = fields[1]
                    else: self.log_debug(11, "Unknown token type for %r", token)
        except Exception, err:
            self.log_debug(1, "Error parsing name file: %s", err)
        else: self.log_debug(11, "Name file loaded")
        name_file.close()
    def restart(self):
        if self.opts.start_sco: self.handle_SCO(self.opts.start_sco)
        if self.opts.start_now: self.handle_NOW(self.opts.start_now)
    
    # Information gathering
    def current_powers(self):
        ''' Returns a list of non-eliminated powers.
            >>> standard_map.powers[ITA].centers = []
            >>> current = standard_map.current_powers(); current.sort()
            >>> for country in current: print country,
            ... 
            AUS ENG FRA GER RUS TUR
        '''#'''
        return [token for token,power in self.powers.iteritems() if power.centers]
    def create_SCO(self):
        ''' Creates a supply center ownership message.
            >>> standard_map.handle_SCO(standard_sco)
            >>> old = standard_sco.fold()
            >>> new = standard_map.create_SCO().fold()
            >>> for item in old:
            ...     if item not in new: print Message(item)
            ... 
            >>> for item in new:
            ...     if item not in old: print Message(item)
            ... 
        '''#'''
        sc_dist = []
        for power in [self.neutral] + self.powers.values():
            if power.centers: sc_dist.insert(0, [power.key] + power.centers)
        # sc_dist.sort()
        return SCO(*sc_dist)
    def create_NOW(self):
        ''' Creates a unit position message.
            >>> now = standard_now.fold()
            >>> then = standard_map.create_NOW().fold()
            >>> for item in then:
            ...     if item not in now: print Message(item)
            ... 
            >>> for item in now:
            ...     if item not in then: print Message(item)
            ... 
            >>> france = standard_map.powers[FRA]
            >>> kiel = standard_map.coasts[(AMY, KIE, None)]
            >>> fk = Unit(france, kiel)
            >>> fk.build()
            >>> fk.retreat([])
            >>> then = standard_map.create_NOW()
            >>> print then.validate(None, 0, True)
            False
            >>> then = then.fold()
            >>> for item in then:
            ...     if item not in now: print Message(item)
            ... 
            FRA AMY KIE MRT ( )
            >>> for item in now:
            ...     if item not in then: print Message(item)
            ... 
            >>> fk.die()
        '''#'''
        units = sum([power.units for power in self.powers.values()], [])
        units.sort()
        return NOW(self.current_turn, *units)
    def ordered_unit(self, nation, unit_spec):
        ''' Finds a unit from its token representation.
            If the specified unit doesn't exist, returns a fake one.
            Accepts any combination of country, unit type, province,
            and coast tokens (even illegal ones); last takes precedence.
            
            >>> Russia = standard_map.powers[RUS]
            >>> print standard_map.ordered_unit(Russia, [RUS, FLT, SEV])
            RUS FLT SEV
            
            # Finds an existing unit, if possible
            >>> print standard_map.ordered_unit(Russia, [RUS, STP])
            RUS FLT ( STP SCS )
            >>> unit = standard_map.ordered_unit(Russia, [MOS])
            >>> print unit
            RUS AMY MOS
            >>> unit.exists()
            True
            >>> print standard_map.ordered_unit(Russia, [BUD])
            AUS AMY BUD
            
            # Country and unit type can be guessed, but only if unambiguous 
            >>> unit = standard_map.ordered_unit(Russia, [AMY, UKR])
            >>> print unit
            RUS AMY UKR
            >>> unit.exists()
            False
            >>> print standard_map.ordered_unit(Russia, [BLA])
            RUS FLT BLA
            >>> unit = standard_map.ordered_unit(Russia, [ARM])
            >>> print unit.coast.unit_type
            None
            >>> unit.exists()
            False
            
            # Will not correct unambiguously wrong orders
            >>> unit = standard_map.ordered_unit(Russia, [RUS, (STP, NCS)])
            >>> print unit
            RUS FLT ( STP NCS )
            >>> unit.exists()
            False
        '''#'''
        # Collect specifications
        country = unit_type = coastline = province = None
        for token in Message(unit_spec):
            if token.is_power():
                country = self.powers.get(token) or Power(token, [])
            elif token.is_province():
                province = self.spaces.get(token) or Province(token, [], None)
            elif token.is_coastline(): coastline = token
            elif token.is_unit_type(): unit_type = token
        if not province:
            raise ValueError, 'Missing province in unit spec: %s' % Message(unit_spec)
        
        # Try to match all specs, but without ambiguity
        unit = None
        for item in province.units:
            if unit_type and item.coast.unit_type != unit_type: continue
            if coastline and item.coast.coastline != coastline: continue
            if country and item.nation != country: continue
            if unit:
                if item.dislodged == unit.dislodged:
                    if item.nation == unit.nation:
                        unit = country = nation = None
                        break
                    elif item.nation == nation: unit = item
                    elif unit.nation != nation:
                        unit = country = nation = None
                        break
                elif item.dislodged: unit = item
            else: unit = item
        if not unit:
            coast = self.coasts.get((unit_type, province.key, coastline))
            if not coast:
                for item in province.coasts:
                    if unit_type and item.unit_type != unit_type: continue
                    if item.coastline != coastline: continue
                    if coast:
                        coast = Coast(None, province, coastline, [])
                        break
                    coast = item
                if not coast: coast = Coast(unit_type, province, coastline, [])
            unit = Unit(country or nation, coast)
        #print '\tordered_unit(%s, %s) -> %s' % (nation, unit_spec, unit)
        return unit
    def ordered_coast(self, unit, coast_spec, datc):
        ''' Finds a coast from its maybe_coast representation.
            If the specified coast doesn't exist, returns a fake one.
            Uses the unit's unit_type, and (depending on options)
            its location to disambiguate bicoastal destinations.
        '''#'''
        # Collect specifications
        unit_type = unit.coast.unit_type
        coastline = province = None
        for token in Message(coast_spec):
            if token.is_province():
                province = self.spaces.get(token) or Province(token, [], None)
            elif token.is_coastline(): coastline = token
        if not province:
            raise ValueError, 'Missing province in coast spec: %s' % Message(coast_spec)
        
        # Try to match all specs, but without ambiguity
        coast = self.coasts.get((unit_type, province.key, coastline))
        if coast:
            if datc.datc_4b3 == 'a' and not unit.can_move_to(coast):
                # Wrong coast specified; change it to the right one.
                possible = [c for c in province.coasts
                        if c.key in unit.coast.borders_out
                        and c.unit_type == unit_type]
                if len(possible) == 1: coast = possible[0]
        else:
            possible = []
            for item in province.coasts:
                if unit_type and item.unit_type != unit_type: continue
                if coastline and item.coastline != coastline: continue
                possible.append(item)
            if len(possible) == 1: coast = possible[0]
            elif possible:
                # Multiple coasts; see whether our location disambiguates.
                # Note that my 4.B.2 "default" coast is the possible one.
                nearby = [c for c in possible if c.key in unit.coast.borders_out]
                if len(nearby) == 1 and datc.datc_4b2 != 'c': coast = nearby[0]
                elif nearby and datc.datc_4b1 == 'b': coast = nearby[0]
            if not coast:
                coast = Coast(None, province, coastline, [])
        #print '\tordered_coast(%s, %s) -> %s (%s, %s, %s)' % (unit, coast_spec, coast, datc.datc_4b1, datc.datc_4b2, datc.datc_4b3)
        return coast
    def distance(self, coast, provs):
        ''' Returns the coast's distance from the nearest of the provinces,
            particularly for use in determining civil disorder retreats.
        '''#'''
        # Todo: Count army and fleet movements differently?
        result = 0
        rank = seen = [coast.province.key]
        def is_home(place, centers=provs): return place in centers
        while rank:
            if any(rank, is_home): return result
            new_rank = []
            for here in rank:
                new_rank.extend([key
                    for key in self.spaces[here].borders_out
                    if key not in seen and key not in new_rank
                ])
            seen.extend(new_rank)
            rank = new_rank
            result += 1
        # Inaccessible island
        return len(self.spaces)  # Essentially infinity
    #distance = Memoize(distance) # Cache results; doesn't work for list args
    def units(self):
        return chain(*[country.units for country in self.powers.values()])
    units = property(fget=units)
    
    # Message handlers
    def handle_MDF(self, message):
        ''' Handles the MDF command, loading province information.
        '''#'''
        if not self.opts.map_mdf: self.opts.map_mdf = message
        self.valid = not self.define(message)
    def handle_SCO(self, message):
        ''' Handles the SCO command, loading center ownership information.
            >>> standard_map.handle_SCO(standard_sco)
            >>> for sc in standard_map.neutral.centers: print sc,
            ... 
            NWY SWE DEN HOL BEL SPA POR TUN GRE SER RUM BUL
            >>> for sc in standard_map.powers[ENG].centers: print sc,
            ... 
            LVP EDI LON
            >>> print standard_map.spaces[NWY].owner
            UNO
            >>> print standard_map.spaces[EDI].owner
            ENG
        '''#'''
        if self.valid:
            sc_dist = message.fold()[1:]
            on_board = Set(self.current_powers())
            for country in [self.neutral] + self.powers.values():
                country.centers = []
            for dist in sc_dist:
                country = dist.pop(0)
                on_board.discard(country)
                power = self.powers.get(country, self.neutral)
                power.centers = dist
                for prov in dist: self.spaces[prov].owner = power
            
            year = self.current_turn.year
            for country in on_board:
                power = self.powers[country]
                if not power.centers: power.eliminated = year
    def handle_NOW(self, message):
        ''' Handles the NOW command, loading turn and unit information.
            May complain about unexpected units.
            
            >>> standard_map.handle_NOW(standard_now)
            >>> English = standard_map.powers[ENG].units; English.sort()
            >>> print ' '.join(['( %s )' % unit for unit in English])
            ( ENG AMY LVP ) ( ENG FLT EDI ) ( ENG FLT LON )
        '''#'''
        folded = message.fold()
        if self.valid:
            self.current_turn.set(*folded[1])
            for prov in self.spaces.itervalues(): prov.units = []
            for country in self.powers.itervalues(): country.units = []
            for unit_spec in folded[2:]:
                (nation,unit_type,loc) = unit_spec[0:3]
                key = location_key(unit_type,loc)
                coast = self.coasts[key]
                power = self.powers[nation]
                unit = Unit(power, coast)
                unit.build()
                if len(unit_spec) > 3: unit.retreat(unit_spec[4])
    def adjust_ownership(self):
        ''' Lets units take over supply centers they occupy.
            Returns a list of countries that gained supply centers.
            
            >>> then = Message(standard_now[:])
            >>> then[21] = RUS
            >>> then[81] = ENG
            >>> standard_map.handle_NOW(then)
            >>> countries = standard_map.adjust_ownership()
            >>> ENG == standard_map.spaces[STP].owner
            True
            >>> RUS == standard_map.spaces[LON].owner
            True
            
            # Restore original map
            >>> standard_map.restart()
        '''#'''
        net_growth = DefaultDict(0)
        for unit in self.units:
            power = unit.nation
            loser = unit.takeover()
            if loser:
                power.eliminated = False
                net_growth[power.key] += 1
                net_growth[loser.key] -= 1
                if not loser.centers:
                    loser.eliminated = self.current_turn.year
        return [token for token,net in net_growth.iteritems() if net > 0]


class Turn(Comparable):
    ''' Represents a single turn, consisting of season and year.
        The following are also available, and may be ANDed with an order token
        to see whether it is valid in the current phase:
            - Turn.move_phase
            - Turn.retreat_phase
            - Turn.build_phase
    '''#'''
    
    opts = config.syntax_options()
    move_phase    = opts.move_phase
    retreat_phase = opts.retreat_phase
    build_phase   = opts.build_phase
    
    def __init__(self, season_list=None):
        self.season_list  = season_list
        self.season_index = None
        self.season = None
        self.year = None
    def set(self, season, year):
        if self.season_list:
            if self.season_index is None or self.year != year:
                self.season_index = self.season_list.index(season)
            else:
                # Just in case a season list uses a season multiple times
                # (Like the baseball variant)
                self.season_index += 1
                try: self.season_index += self.season_list[self.season_index:].index(season)
                except ValueError: self.season_index = self.season_list.index(season)
        self.season = season
        self.year   = year
    def advance(self):
        ''' Changes to the next turn, advancing the year if appropriate.
        '''#'''
        if self.season_list:
            seasons = len(self.season_list)
            self.season_index += 1
            if self.season_index >= seasons:
                self.season_index %= seasons
                self.year += 1
            self.season = self.season_list[self.season_index]
        else: raise UserWarning, 'Turn.advance() can only be called on Turns created with a season list.'
    def __str__(self): return '(%s %s)' % self.key
    def tokenize(self): return list(self.key)
    def phase(self):
        ''' Returns the phase of the current turn
            (that is, movement, retreat, or adjustment)
            as one of the values move_phase, retreat_phase, or build_phase.
            
            >>> t = Turn(); t.set(SUM, 1901); print t, hex(t.phase())
            (SUM 1901) 0x40
            >>> t.phase() == Turn.retreat_phase
            True
        '''#'''
        try: return config.order_mask[self.season]
        except KeyError:
            # Not defined by the DAIDE, so make an assumption
            return self.season.value() & config.order_mask[None]
    def __cmp__(self, other):
        ''' Compares Turns with each other, or with their keys.
            >>> ts = Turn(); ts.set(SPR, Token(1901))
            >>> tf = Turn(); tf.set(FAL, Token(1901))
            >>> cmp(ts, tf)
            -1
            >>> cmp(tf, ts.key)
            1
            >>> cmp(tf, tf.key)
            0
            >>> Turn() < [SPR, 1901]
            True
        '''#'''
        if not self.season: return -1
        if isinstance(other, Turn):
            season = other.season
            year = other.year
        else:
            try: season, year = tuple(other)
            except: return NotImplemented
        if self.year == year and self.season != season:
            if self.season_list:
                return cmp(self.season_index, self.season_list.index(season))
            else: return cmp(self.season.value(), season.value())
        else: return cmp(self.year, year)
    def key(self): return (self.season, self.year)
    key = property(fget=key)


class Power(Comparable):
    ''' Represents a country in the game.
        Variables:
            - key        the Token that represents this power
            - homes      list of Tokens for home supply centers
            - centers    list of Tokens for supply centers controlled
            - units      list of Units owned
            - eliminated year of elimination, or False if still on the board
    '''#'''
    def __init__(self, token, home_scs):
        self.key        = token
        self.name       = token.text
        self.homes      = home_scs
        self.units      = []
        self.centers    = []
        self.adjective  = self.name
        self.eliminated = False
    def __cmp__(self, other):
        ''' Allows direct comparison of Powers and tokens.
            Note: This doesn't fully work for new-style classes.
            >>> country = Power(ENG, [])
            >>> country == ENG
            True
            >>> country == Token('Eng', 0x4101)
            False
            >>> country == Power(ENG, [NWY])
            True
            >>> pows = [Power(UNO, []), Power(FRA, [PAR]), None, country]
            >>> pows.sort()
            >>> print ' '.join([str(item) for item in pows])
            ENG FRA UNO None
        '''#'''
        if other is None:              return -1
        elif isinstance(other, Token): return cmp(self.key, other)
        elif isinstance(other, Power): return cmp(self.key, other.key)
        else: return NotImplemented 
    def tokenize(self): return [self.key]
    def __str__(self): return self.name
    def __repr__(self): return 'Power(%s, %s)' % (self.key, self.homes)
    
    def surplus(self):
        ''' Returns the number of unsupplied units owned by the power.
            Usually, this is the number of units that must be removed.
            Negative numbers indicate that builds are in order.
            
            >>> italy = standard_map.powers[ITA]
            >>> print italy.surplus()
            0
            >>> italy.centers = [ROM]; print italy.surplus()
            2
            >>> italy.centers = [ROM, TUN, VEN, NAP, GRE]; print italy.surplus()
            -2
        '''#'''
        return len(self.units) - len(self.centers)
    def farthest_units(self, distance):
        ''' Returns a list of units in order of removal preference,
            for a power that hasn't ordered enough removals.
        '''#'''
        # Todo: the Chaos variant should use self.centers instead of self.homes
        dist_list = [(
            -distance(unit.coast, self.homes), # Farthest unit
            -unit.coast.unit_type.number,      # Fleets before armies
            unit.coast.province.key.text,      # First alphabetically
            unit
        ) for unit in self.units]
        dist_list.sort()
        return [item[3] for item in dist_list]


class Province(Comparable):
    ''' Represents a space of the board.
        Variables:
            - key          The Token representing this province
            - homes        A list of powers for which this is a Home Supply Center
            - coasts       A list of Coasts
            - owner        The power that controls this supply center
            - borders_in   The provinces that can reach this one
            - borders_out  The provinces that can be reached from here
            - units        A list of Units here
    '''#'''
    def __init__(self, token, adjacencies, owners):
        self.key         = token
        self.name        = token.text
        self.homes       = owners
        self.coasts      = []
        self.units       = []
        self.owner       = None
        self.borders_in  = Set()
        self.borders_out = Set()
        for unit_adjacency in adjacencies:
            unit = unit_adjacency.pop(0)
            if isinstance(unit, list):
                coast = unit[1]
                unit_type = unit[0]
            else:
                coast = None
                unit_type = unit
            new_coast = Coast(unit_type, self, coast, unit_adjacency)
            self.coasts.append(new_coast)
            self.borders_out.update([key[1] for key in new_coast.borders_out])
    
    def is_supply(self): return self.homes is not None
    def is_valid(self):
        if self.homes and not self.key.is_supply(): return False
        if not self.coasts: return False
        return all(self.coasts, Coast.is_valid)
    def is_coastal(self):
        if self.key.is_coastal(): return location_key(AMY, self.key)
        else: return None
    def can_convoy(self): return self.key.category_name() in ('Sea SC', 'Sea non-SC')
    def __str__(self): return self.name
    def __repr__(self): return "Province('%s')" % self.name
    def tokenize(self): return [self.key]
    def __cmp__(self, other):
        ''' Compares Provinces with each other, or with their tokens.
            >>> LVP == standard_map.spaces[LVP]
            True
        '''#'''
        if isinstance(other, Token):      return cmp(self.key, other)
        elif isinstance(other, Province): return cmp(self.key, other.key)
        else: return NotImplemented 
    def exists(self): return bool(self.coasts)


class Coast(Comparable, Verbose_Object):
    ''' A place where a unit can be.
        Each Province has one per unit type allowed there,
        with extra fleet Coasts for multi-coastal provinces.
        
        Variables:
            - unit_type    The type of unit (AMY or FLT)
            - province     The Province
            - coastline    The coast represented (SCS, etc.), or None
            - borders_in   A list of keys for coasts which could move to this one
            - borders_out  A list of keys for coasts to which this unit could move
            - key          A tuple that uniquely specifies this coast
            - maybe_coast  (province, coast) for bicoastal provinces, province for others
    '''#'''
    def __init__(self, unit_type, province, coastline, adjacencies):
        # Warning: a fake Coast can have a unit_type of None.
        self.unit_type   = unit_type
        self.coastline   = coastline
        self.province    = province
        self.key         = (unit_type, province.key, coastline)
        self.borders_in  = Set()
        self.borders_out = [location_key(unit_type, adj) for adj in adjacencies]
        if coastline:
            self.maybe_coast = (province.key, coastline)
            self.text        = '(%s (%s %s))' % (unit_type, province.key, coastline)
        else:
            self.maybe_coast = province.key
            self.text        = '(%s %s)' % (unit_type, province.key)
    
    def tokenize(self):
        return Message([self.unit_type, self.maybe_coast])
    def __cmp__(self, other):
        if isinstance(other, Coast): return cmp(self.key, other.key)
        else: return NotImplemented
    def __str__(self): return self.text
    def __repr__(self): return 'Coast(%s, %s, %s)' % self.key
    def prefix(self):
        if self.coastline:
            line = self.coastline.text.lower()
            if line[-1] == 's': line = line[:-1]
            coast = ' (%s)' % line
        else: coast = ''
        return '%s %s%s' % (self.unit_type.text[0], self.province.name, coast)
    prefix = property(fget=prefix)
    
    # Confirmation queries
    def is_valid(self):
        category = self.province.key.category_name().split()[0]
        if self.coastline:
            return (category == 'Bicoastal' and self.unit_type == FLT
                and self.coastline.category_name() == 'Coasts')
        elif category == 'Sea':       return self.unit_type == FLT
        elif category == 'Inland':    return self.unit_type == AMY
        elif category == 'Bicoastal': return self.unit_type == AMY
        elif category == 'Coastal':   return self.unit_type in (AMY, FLT)
        else:                         return False
    def exists(self): return self.unit_type and self in self.province.coasts
    def convoy_routes(self, dest, board):
        ''' Collects possible convoy routes.
            dest must be a Province.
            Each route is a tuple of Province instances.
            Now collects only routes that currently have fleets.
        '''#'''
        self.log_debug(11, 'Collecting convoy routes to %s', dest.name)
        path_list = []
        if self.province != dest and dest.is_coastal():
            possible = [(p,)
                for p in [board.spaces[key] for key in self.province.borders_out]
                if p.can_convoy() and len(p.units) > 0
            ]
            while possible:
                route = possible.pop()
                self.log_debug(12, 'Considering %s',
                        ' -> '.join([prov.name for prov in route]))
                here = route[-1]
                if dest.key in here.borders_out: path_list.append(route)
                seen = [p.key for p in route]
                possible.extend([route + (p,)
                    for p in [board.spaces[key]
                        for key in here.borders_out
                        if key not in seen]
                    if p.can_convoy() and len(p.units) > 0
                ])
            # Sort shorter paths to the front,
            # to speed up checking
            path_list.sort(lambda x,y: cmp(len(x), len(y)))
        self.log_debug(11, 'Routes found: %s', path_list)
        return path_list
    def matches(self, key):
        #print '\tmatches(%s, %s)' % (self.key, key)
        return (self.key == key) or (self.unit_type is None
                and self.key[1] == key[1])


class Unit(Comparable):
    ''' A unit on the board.
        Technically, units don't track past state, but these can.
    '''#'''
    def __init__(self, nation, coast):
        # Warning: a fake Unit can have a nation of None.
        self.coast       = coast
        self.nation      = nation
        self.dislodged   = False
        self.retreats    = None
    
    # Representations
    def tokenize(self):
        result = Message(self.key)
        if self.dislodged: result.extend(MRT(self.retreats))
        return result
    def __str__(self): return str(Message(self))
    def __repr__(self): return 'Unit(%s, %r)' % (self.nation, self.coast)
    def __cmp__(self, other):
        if isinstance(other, Unit):
            return (cmp(self.nation, other.nation)
                    or cmp(self.coast, other.coast))
        else: return NotImplemented
    def key(self):
        return (self.nation and self.nation.key,
                self.coast and self.coast.unit_type,
                self.coast and self.coast.maybe_coast)
    key = property(fget=key)
    
    # Actions
    def move_to(self, coast):
        # Update the Provinces
        self.coast.province.units.remove(self)
        coast.province.units.append(self)
        
        # Update the Unit
        self.coast     = coast
        self.dislodged = False
        self.retreats  = None
    def retreat(self, retreats):
        self.dislodged   = True
        self.retreats    = retreats
    def build(self):
        self.nation.units.append(self)
        self.coast.province.units.append(self)
    def die(self):
        self.nation.units.remove(self)
        self.coast.province.units.remove(self)
    def takeover(self):
        ''' Takes control of the current space.
            If control of a supply center changes,
            returns the former controller.
        '''#'''
        prov = self.coast.province
        if prov.is_supply():
            former = prov.owner
            if former != self.nation:
                prov.owner = self.nation
                self.nation.centers.append(prov.key)
                former.centers.remove(prov.key)
                return former
        return None
    
    # Confirmation queries
    def can_move_to(self, place):
        #print '\tQuery: %s -> %s' % (self, place)
        if isinstance(place, Coast):
            # Check whether it can move to any coastline
            return any(self.coast.borders_out, place.matches)
        else:
            # Assume a Province or province token
            return place.key in [key[1] for key in self.coast.borders_out]
        return False
    def can_convoy(self):
        return self.coast.unit_type == FLT and self.coast.province.can_convoy()
    def can_be_convoyed(self):
        return self.coast.unit_type == AMY and self.coast.province.is_coastal()
    def exists(self): return self in self.coast.province.units


def _test():
    ''' Exercises the doctests above.
        For convenience and time, standard_map and its tokens
        are added to the global dictionary.
    '''#'''
    import doctest, gameboard
    globs = config.extend_globals(gameboard.__dict__)
    return doctest.testmod(gameboard, globs=globs)
if __name__ == "__main__": _test()

# vim: sts=4 sw=4 et tw=75 fo=crql1
