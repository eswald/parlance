r'''Non-DATC test cases for the Parlance judge
    Copyright (C) 2004-2009  Eric Wald
    
    This module tests basic judge functionality, including DAIDE requirements
    and implementation-specific details, beyond the adjudication.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

import unittest
from time import time

from nose.tools import timed

from parlance.config    import variants, Configuration, GameOptions
from parlance.judge     import Attack_Decision, Hold_Decision, \
        Move_Decision, Path_Decision, Prevent_Decision
from parlance.language  import Token
from parlance.orders    import MoveOrder, OrderSet, createUnitOrder
from parlance.tokens    import *
from parlance.xtended   import *
        
from parlance.test import fails
from parlance.test.datc import DiplomacyAdjudicatorTestCase
from parlance.test.gameboard import load_variant

SWI = Token('SWI', 0x504B)

class Judge_Movement(DiplomacyAdjudicatorTestCase):
    ''' Judge movement phase adjudication'''
    def test_army_move_inland(self):
        ''' Army movement to adjacent inland sector'''
        self.init_state(SPR, 1901, [
            [RUS, AMY, MOS],
        ])
        self.legalOrder(RUS, [(RUS, AMY, MOS), MTO, WAR])
        self.assertMapState([
            [RUS, AMY, WAR],
        ])
    def test_army_move_coastal(self):
        ''' Army movement to adjacent coastal sector'''
        self.init_state(SPR, 1901, [
            [RUS, AMY, SEV],
        ])
        self.legalOrder(RUS, [(RUS, AMY, SEV), MTO, RUM])
        self.assertMapState([
            [RUS, AMY, RUM],
        ])
    def test_army_move_overland(self):
        ''' Army movement to adjacent overland sector'''
        self.init_state(SPR, 1901, [
            [ITA, AMY, VEN],
        ])
        self.legalOrder(ITA, [(ITA, AMY, VEN), MTO, ROM])
        self.assertMapState([
            [ITA, AMY, ROM],
        ])
    def test_fleet_move_coastal(self):
        ''' Fleet movement to adjacent coastal sector'''
        self.init_state(SPR, 1901, [
            [RUS, FLT, SEV],
        ])
        self.legalOrder(RUS, [(RUS, FLT, SEV), MTO, RUM])
        self.assertMapState([
            [RUS, FLT, RUM],
        ])
    def test_fleet_move_sea(self):
        ''' Fleet movement to adjacent sea sector'''
        self.init_state(SPR, 1901, [
            [RUS, FLT, BAR],
        ])
        self.legalOrder(RUS, [(RUS, FLT, BAR), MTO, NWG])
        self.assertMapState([
            [RUS, FLT, NWG],
        ])
    def test_move_support(self):
        ''' Movement with support to dislodge'''
        self.init_state(SPR, 1901, [
            [RUS, AMY, MOS],
            [RUS, AMY, UKR],
            [GER, AMY, WAR],
        ])
        self.legalOrder(RUS, [(RUS, AMY, MOS), SUP, (RUS, AMY, UKR), MTO, WAR])
        self.legalOrder(RUS, [(RUS, AMY, UKR), MTO, WAR])
        self.legalOrder(GER, [(GER, AMY, WAR), HLD])
        self.assertMapState([
            [RUS, AMY, MOS],
            [RUS, AMY, WAR],
            [GER, AMY, WAR, MRT],
        ])
    def test_hold_support(self):
        ''' Holding with support against supported attack'''
        start_state = [
            [RUS, AMY, MOS],
            [RUS, AMY, UKR],
            [GER, AMY, WAR],
            [GER, AMY, PRU],
        ]
        self.init_state(SPR, 1901, start_state)
        self.legalOrder(RUS, [(RUS, AMY, MOS), SUP, (RUS, AMY, UKR), MTO, WAR])
        self.legalOrder(RUS, [(RUS, AMY, UKR), MTO, WAR])
        self.legalOrder(GER, [(GER, AMY, WAR), HLD])
        self.legalOrder(GER, [(GER, AMY, PRU), SUP, (GER, AMY, WAR), HLD])
        self.assertMapState(start_state)
    def test_convoy(self):
        ''' Basic convoy'''
        self.init_state(SPR, 1901, [
            [ENG, FLT, ECH],
            [ENG, AMY, LON],
        ])
        self.legalOrder(ENG, [(ENG, AMY, LON), CTO, BRE, VIA, [ECH]])
        self.legalOrder(ENG, [(ENG, FLT, ECH), CVY, (ENG, AMY, LON), CTO, BRE])
        self.assertMapState([
            [ENG, FLT, ECH],
            [ENG, AMY, BRE],
        ])
    def test_support_coastless(self):
        ''' Support to move to an unspecified, ambiguous coast'''
        steady_state = [
            [FRA, FLT, GOL],
            [GER, AMY, MAR],
            [GER, AMY, GAS],
            [ITA, FLT, POR],
        ]
        self.init_state(SPR, 1901, steady_state)
        self.legalOrder(FRA, [(FRA, FLT, GOL), SUP, (ITA, FLT, POR), MTO, SPA])
        self.legalOrder(GER, [(GER, AMY, MAR), SUP, (GER, AMY, GAS), MTO, SPA])
        self.legalOrder(GER, [(GER, AMY, GAS), MTO, SPA])
        self.legalOrder(ITA, [(ITA, FLT, POR), MTO, (SPA, NCS)])
        self.assertMapState(steady_state)
    def test_beleagured(self):
        ''' Massive beleagured garrison situation
            Presented by David Norman
        '''#'''
        steady_state = [
            [ENG, FLT, ECH],
            [ENG, FLT, LON],
            [ENG, FLT, YOR],
            [ENG, FLT, EDI],
            
            [RUS, FLT, NWY],
            [RUS, FLT, NWG],
            [RUS, FLT, SKA],
            [RUS, FLT, DEN],
            
            [GER, FLT, NTH],
            [GER, FLT, BEL],
            [GER, FLT, PIC],
            
            [FRA, FLT, BRE],
            [FRA, FLT, MAO],
        ]
        self.init_state(SPR, 1901, steady_state)
        self.legalOrder(ENG, [(ENG, FLT, ECH), MTO, NTH])
        self.legalOrder(ENG, [(ENG, FLT, LON), SUP, (ENG, FLT, ECH), MTO, NTH])
        self.legalOrder(ENG, [(ENG, FLT, YOR), SUP, (ENG, FLT, ECH), MTO, NTH])
        self.legalOrder(ENG, [(ENG, FLT, EDI), SUP, (ENG, FLT, ECH), MTO, NTH])
        
        self.legalOrder(RUS, [(RUS, FLT, NWY), MTO, NTH])
        self.legalOrder(RUS, [(RUS, FLT, NWG), SUP, (RUS, FLT, NWY), MTO, NTH])
        self.legalOrder(RUS, [(RUS, FLT, SKA), SUP, (RUS, FLT, NWY), MTO, NTH])
        self.legalOrder(RUS, [(RUS, FLT, DEN), SUP, (RUS, FLT, NWY), MTO, NTH])
        
        self.legalOrder(GER, [(GER, FLT, NTH), MTO, ECH])
        self.legalOrder(GER, [(GER, FLT, BEL), SUP, (GER, FLT, NTH), MTO, ECH])
        self.legalOrder(GER, [(GER, FLT, PIC), SUP, (GER, FLT, NTH), MTO, ECH])
        
        self.legalOrder(FRA, [(FRA, FLT, BRE), MTO, ECH])
        self.legalOrder(FRA, [(FRA, FLT, MAO), SUP, (FRA, FLT, BRE), MTO, ECH])
        self.assertMapState(steady_state)
    def test_dptg_bug(self):
        ''' Listed in the DAIDE introduction as a required bugfix.
            The DPTG algorithm apparently gets this wrong.
        '''#'''
        steady_state = [
            [ENG, FLT, DEN],
            [ENG, FLT, SKA],
            [RUS, FLT, SWE],
            [RUS, FLT, BAL],
            [GER, FLT, KIE],
            [GER, FLT, HEL],
        ]
        self.init_state(SPR, 1901, steady_state)
        self.legalOrder(ENG, [(ENG, FLT, DEN), MTO, KIE])
        self.legalOrder(ENG, [(ENG, FLT, SKA), SUP, (RUS, FLT, SWE), MTO, DEN])
        
        self.legalOrder(RUS, [(RUS, FLT, SWE), MTO, DEN])
        self.legalOrder(RUS, [(RUS, FLT, BAL), SUP, (RUS, FLT, SWE), MTO, DEN])
        
        self.legalOrder(GER, [(GER, FLT, KIE), MTO, DEN])
        self.legalOrder(GER, [(GER, FLT, HEL), SUP, (GER, FLT, KIE), MTO, DEN])
        self.assertMapState(steady_state)

class Judge_Convoys(DiplomacyAdjudicatorTestCase):
    ''' Minute details of convoy adjudication'''
    game_options = {
        'send_ORD': True,
        'AOA': False,
    }
    
    def assertOrdered(self, order):
        orders = [msg for msg in self.results if msg[0] is ORD]
        self.assertContains(orders, order)
    
    def test_pathless_convoy(self):
        ''' Convoy orders can be sent without a path'''
        self.init_state(SPR, 1901, [
            [ENG, FLT, ECH],
            [ENG, AMY, LON],
        ])
        self.legalOrder(ENG, [(ENG, AMY, LON), CTO, BRE])
        self.legalOrder(ENG, [(ENG, FLT, ECH), CVY, (ENG, AMY, LON), CTO, BRE])
        self.assertMapState([
            [ENG, FLT, ECH],
            [ENG, AMY, BRE],
        ])
    def test_successful_convoy_path(self):
        ''' Successful pathless convoys have a good path in the ORD message'''
        self.init_state(SPR, 1901, [
            [ENG, FLT, ECH],
            [ENG, AMY, LON],
        ])
        self.legalOrder(ENG, [(ENG, AMY, LON), CTO, BRE])
        self.legalOrder(ENG, [(ENG, FLT, ECH), CVY, (ENG, AMY, LON), CTO, BRE])
        self.assertMapState([
            [ENG, FLT, ECH],
            [ENG, AMY, BRE],
        ])
        self.assertOrdered(ORD (SPR, 1901)
            ([ENG, AMY, LON], CTO, BRE, VIA, [ECH]) (SUC))
    def test_disrupted_convoy_path(self):
        ''' Disrupted pathless convoys have a valid path in the ORD message'''
        self.init_state(SPR, 1901, [
            [ENG, FLT, ECH],
            [ENG, AMY, LON],
            [FRA, FLT, MAO],
            [FRA, FLT, BRE],
        ])
        self.legalOrder(ENG, [(ENG, AMY, LON), CTO, BEL])
        self.legalOrder(ENG, [(ENG, FLT, ECH), CVY, (ENG, AMY, LON), CTO, BEL])
        self.legalOrder(FRA, [(FRA, FLT, MAO), MTO, ECH])
        self.legalOrder(FRA, [(FRA, FLT, BRE), SUP, (FRA, FLT, MAO), MTO, ECH])
        self.assertMapState([
            [ENG, FLT, ECH, MRT],
            [ENG, AMY, LON],
            [FRA, FLT, ECH],
            [FRA, FLT, BRE],
        ])
        self.assertOrdered(ORD (SPR, 1901)
            ([ENG, AMY, LON], CTO, BEL, VIA, [ECH]) (DSR))
    def test_ignored_convoy_path(self):
        ''' A convoy with a specified path ignores other possible paths'''
        self.init_state(SPR, 1901, [
            [ENG, FLT, NTH],
            [ENG, FLT, ECH],
            [ENG, AMY, LON],
            [FRA, FLT, MAO],
            [FRA, FLT, BRE],
        ])
        self.legalOrder(ENG, [(ENG, AMY, LON), CTO, BEL, VIA, [ECH]])
        self.legalOrder(ENG, [(ENG, FLT, ECH), CVY, (ENG, AMY, LON), CTO, BEL])
        self.legalOrder(ENG, [(ENG, FLT, NTH), CVY, (ENG, AMY, LON), CTO, BEL])
        self.legalOrder(FRA, [(FRA, FLT, MAO), MTO, ECH])
        self.legalOrder(FRA, [(FRA, FLT, BRE), SUP, (FRA, FLT, MAO), MTO, ECH])
        self.assertMapState([
            [ENG, FLT, NTH],
            [ENG, FLT, ECH, MRT],
            [ENG, AMY, LON],
            [FRA, FLT, ECH],
            [FRA, FLT, BRE],
        ])
        self.assertOrdered(ORD (SPR, 1901)
            ([ENG, AMY, LON], CTO, BEL, VIA, [ECH]) (DSR))
    def test_convoy_path_repeated(self):
        ''' A convoy with a specified path uses that path in the ORD message'''
        self.init_state(SPR, 1901, [
            [ENG, FLT, NTH],
            [ENG, FLT, ECH],
            [ENG, AMY, LON],
        ])
        self.legalOrder(ENG, [(ENG, AMY, LON), CTO, BEL, VIA, [ECH]])
        self.legalOrder(ENG, [(ENG, FLT, ECH), CVY, (ENG, AMY, LON), CTO, BEL])
        self.legalOrder(ENG, [(ENG, FLT, NTH), CVY, (ENG, AMY, LON), CTO, BEL])
        self.assertMapState([
            [ENG, FLT, NTH],
            [ENG, FLT, ECH],
            [ENG, AMY, BEL],
        ])
        self.assertOrdered(ORD (SPR, 1901)
            ([ENG, AMY, LON], CTO, BEL, VIA, [ECH]) (SUC))
    def test_unmatched_convoy_path(self):
        ''' Unconvoyed pathless convoys have a reasonable path in the ORD message'''
        self.init_state(SPR, 1901, [
            [ENG, FLT, ECH],
            [ENG, AMY, LON],
        ])
        self.legalOrder(ENG, [(ENG, AMY, LON), CTO, BEL])
        self.legalOrder(ENG, [(ENG, FLT, ECH), MTO, BRE])
        self.assertMapState([
            [ENG, FLT, BRE],
            [ENG, AMY, LON],
        ])
        self.assertOrdered(ORD (SPR, 1901)
            ([ENG, AMY, LON], CTO, BEL, VIA, [ECH]) (NSO))
    def test_partly_disrupted_convoy_path(self):
        ''' A convoy with one disrupted path shows that when disrupted'''
        self.judge.datc.datc_4a1 = 'a'
        self.init_state(SPR, 1901, [
            [ENG, FLT, NTH],
            [ENG, FLT, ECH],
            [ENG, AMY, LON],
            [GER, FLT, DEN],
            [GER, FLT, HOL],
        ])
        self.legalOrder(ENG, [(ENG, AMY, LON), CTO, BEL])
        self.legalOrder(ENG, [(ENG, FLT, ECH), CVY, (ENG, AMY, LON), CTO, BEL])
        self.legalOrder(ENG, [(ENG, FLT, NTH), CVY, (ENG, AMY, LON), CTO, BEL])
        self.legalOrder(GER, [(GER, FLT, DEN), MTO, NTH])
        self.legalOrder(GER, [(GER, FLT, HOL), SUP, (GER, FLT, DEN), MTO, NTH])
        self.assertMapState([
            [ENG, FLT, ECH],
            [ENG, FLT, NTH, MRT],
            [ENG, AMY, LON],
            [GER, FLT, NTH],
            [GER, FLT, HOL],
        ])
        self.assertOrdered(ORD (SPR, 1901)
            ([ENG, AMY, LON], CTO, BEL, VIA, [NTH]) (DSR))
    def test_convoyed_move_order(self):
        ''' Move orders get changed to convoy orders when actually convoyed'''
        self.judge.datc.datc_4a3 = 'd'
        self.init_state(SPR, 1901, [
            [ENG, FLT, ECH],
            [ENG, AMY, LON],
        ])
        self.legalOrder(ENG, [(ENG, AMY, LON), MTO, BEL])
        self.legalOrder(ENG, [(ENG, FLT, ECH), CVY, (ENG, AMY, LON), CTO, BEL])
        self.assertMapState([
            [ENG, FLT, ECH],
            [ENG, AMY, BEL],
        ])
        self.assertOrdered(ORD (SPR, 1901)
            ([ENG, AMY, LON], CTO, BEL, VIA, [ECH]) (SUC))
    def test_swapping_convoy_path(self):
        ''' Move orders to adjacent provinces can get changed to convoy orders'''
        self.judge.datc.datc_4a3 = 'd'
        steady_state = [
            [ITA, FLT, TYS],
            [TUR, FLT, ION],
        ]
        self.init_state(SPR, 1901, steady_state + [
            [ITA, AMY, ROM],
            [TUR, AMY, APU],
        ])
        self.legalOrder(ITA, [(ITA, AMY, ROM), MTO, APU])
        self.legalOrder(ITA, [(ITA, FLT, TYS), CVY, (TUR, AMY, APU), CTO, ROM])
        self.legalOrder(TUR, [(TUR, AMY, APU), MTO, ROM])
        self.legalOrder(TUR, [(TUR, FLT, ION), CVY, (TUR, AMY, APU), CTO, ROM])
        self.assertMapState(steady_state + [
            [ITA, AMY, APU],
            [TUR, AMY, ROM],
        ])
        self.assertOrdered(ORD (SPR, 1901)
            ([TUR, AMY, APU], CTO, ROM, VIA, [ION, TYS]) (SUC))
    def test_oneway_convoy_paths(self):
        # Every step of the convoy by the army must be a move
        # that is allowed for fleets moving in that direction.
        #
        # The following examples are all one-way trips:
        # AAA  -> SSS <-> YYY <-> BBB
        # AAA <-> TTT  -> YYY <-> BBB
        # AAA <-> TTT <-> ZZZ  -> BBB
        
        variant = load_variant('''
            [homes]
            ONE=AAA
            TWO=BBB
            TRE=CCC
            
            [borders]
            AAA=AMY CCC, FLT SSS TTT
            BBB=AMY CCC, FLT YYY
            CCC=AMY AAA BBB
            SSS=FLT YYY
            TTT=FLT AAA YYY ZZZ
            YYY=FLT BBB SSS
            ZZZ=FLT BBB TTT
        ''')
        
        rep = variant.rep
        ONE = rep["ONE"]
        TWO = rep["TWO"]
        TRE = rep["TRE"]
        AAA = rep["AAA"]
        BBB = rep["BBB"]
        SSS = rep["SSS"]
        TTT = rep["TTT"]
        YYY = rep["YYY"]
        ZZZ = rep["ZZZ"]
        
        self.judge = variant.new_judge(GameOptions())
        self.judge.start()
        self.init_state(SPR, 1901, [
            [ONE, AMY, AAA],
            [TWO, AMY, BBB],
            [TRE, FLT, SSS],
            [TRE, FLT, TTT],
            [TRE, FLT, YYY],
            [TRE, FLT, ZZZ],
        ])
        
        self.legalOrder(ONE, [(ONE, AMY, AAA), CTO, BBB, VIA, [SSS, YYY]])
        self.legalOrder(ONE, [(ONE, AMY, AAA), CTO, BBB, VIA, [TTT, YYY]])
        self.legalOrder(ONE, [(ONE, AMY, AAA), CTO, BBB, VIA, [TTT, ZZZ]])
        self.illegalOrder(TWO, [(TWO, AMY, BBB), CTO, AAA, VIA, [YYY, SSS]])
        self.illegalOrder(TWO, [(TWO, AMY, BBB), CTO, AAA, VIA, [YYY, TTT]])
        self.illegalOrder(TWO, [(TWO, AMY, BBB), CTO, AAA, VIA, [ZZZ, TTT]])

class Judge_Basics(DiplomacyAdjudicatorTestCase):
    ''' Basic Judge Functionality'''
    game_options = {'LVL': 0, 'PDA': True}
    def acceptable(self, country, message):
        client = self.Fake_Service(country)
        method_name = 'handle_' + message[0].text
        if message[0] in (YES, REJ, NOT): method_name += '_' + message[2].text
        getattr(self.judge, method_name)(client, message)
        self.assertContains(client.replies, YES(message))
    def assertRetreats(self, prov, retreats):
        space = self.judge.map.spaces[prov.key]
        valid = sum([(unit.retreats or []) for unit in space.units], [])
        self.failUnlessEqual(set(retreats), set(valid))
    def assertDrawn(self, *countries):
        winners = set(countries)
        messages = self.judge.run()
        for msg in messages:
            if msg[0] is DRW:
                self.failUnlessEqual(winners, set(msg[2:-1]))
                break
        else: raise self.failureException, 'No draw message in %s' % (messages,)
    def assertNotDrawn(self):
        messages = self.judge.run()
        for msg in messages:
            if msg[0] is DRW:
                raise self.fail(msg)
    
    def test_disordered_draws(self):
        ''' Draws with different order still the same'''
        self.judge.game_opts.PDA = True
        self.init_state(SPR, 1901, [
            [RUS, AMY, MOS],
            [ENG, FLT, LON],
            [FRA, AMY, PAR],
            [GER, AMY, BER],
            [ITA, AMY, ROM],
            [TUR, FLT, CON],
            [AUS, AMY, VIE],
        ])
        self.acceptable(RUS, DRW(RUS, ENG, FRA))
        self.acceptable(ENG, DRW(ENG, RUS, FRA))
        self.acceptable(FRA, DRW(RUS, FRA, ENG))
        self.acceptable(GER, DRW(FRA, RUS, ENG))
        self.acceptable(ITA, DRW(FRA, ENG, RUS))
        self.acceptable(TUR, DRW(ENG, FRA, RUS))
        self.acceptable(AUS, DRW(FRA, RUS, ENG))
        self.assertDrawn(FRA, ENG, RUS)
    def test_draw_cancellation(self):
        # Clients can cancel a specific draw request
        self.judge.game_opts.PDA = True
        self.init_state(SPR, 1901, [
            [RUS, AMY, MOS],
            [ENG, FLT, LON],
            [FRA, AMY, PAR],
            [GER, AMY, BER],
            [ITA, AMY, ROM],
            [TUR, FLT, CON],
            [AUS, AMY, VIE],
        ])
        
        msg = DRW(ENG, FRA, RUS)
        self.acceptable(RUS, msg)
        self.acceptable(ENG, msg)
        self.acceptable(FRA, msg)
        self.acceptable(GER, msg)
        self.acceptable(ITA, msg)
        self.acceptable(ENG, NOT(msg))
        self.acceptable(TUR, msg)
        self.acceptable(AUS, msg)
        self.assertNotDrawn()
    def test_retreat_coasts(self):
        ''' Fleets retreat to specific coasts'''
        self.init_state(SPR, 1901, [
            [ENG, FLT, GAS],
            [FRA, AMY, PAR],
            [FRA, AMY, MAR],
        ])
        self.legalOrder(ENG, [(ENG, FLT, GAS), HLD])
        self.legalOrder(FRA, [(FRA, AMY, MAR), MTO, GAS])
        self.legalOrder(FRA, [(FRA, AMY, PAR), SUP, (FRA, AMY, MAR), MTO, GAS])
        self.assertMapState([
            [ENG, FLT, GAS, MRT],
            [FRA, AMY, PAR],
            [FRA, AMY, GAS],
        ])
        self.assertRetreats(GAS, [BRE, MAO, (SPA, NCS)])
    def test_retreat_contested(self):
        ''' Units cannot retreat to contested areas'''
        steady_state = [
            [FRA, AMY, PAR],
            [FRA, AMY, PIC],
        ]
        self.init_state(SPR, 1901, steady_state + [
            [ENG, FLT, GAS],
            [FRA, AMY, MAR],
        ])
        self.legalOrder(ENG, [(ENG, FLT, GAS), MTO, BRE])
        self.legalOrder(FRA, [(FRA, AMY, PIC), MTO, BRE])
        self.legalOrder(FRA, [(FRA, AMY, MAR), MTO, GAS])
        self.legalOrder(FRA, [(FRA, AMY, PAR), SUP, (FRA, AMY, MAR), MTO, GAS])
        self.assertMapState(steady_state + [
            [ENG, FLT, GAS, MRT],
            [FRA, AMY, GAS],
        ])
        self.illegalOrder(ENG, [(ENG, FLT, GAS), RTO, BRE])
        self.assertMapState(steady_state + [
            [FRA, AMY, GAS],
        ])
    def test_multiple_builds(self):
        ''' Only one unit can be built in a supply center'''
        steady_state = [
            [FRA, AMY, PAR],
        ]
        self.init_state(WIN, 1901, steady_state)
        self.legalOrder(FRA, [(FRA, AMY, MAR), BLD])
        self.illegalOrder(FRA, [(FRA, AMY, MAR), BLD])
        self.illegalOrder(FRA, [(FRA, FLT, MAR), BLD])
        self.assertMapState(steady_state + [
            [FRA, AMY, MAR],
        ])
    def test_waives(self):
        ''' Builds can be waived without error'''
        steady_state = [
            [FRA, AMY, PAR],
        ]
        self.init_state(WIN, 1901, steady_state)
        self.legalOrder(FRA, [FRA, WVE])
        self.legalOrder(FRA, [(FRA, AMY, MAR), BLD])
        self.illegalOrder(FRA, [(FRA, AMY, BRE), BLD])
        self.assertMapState(steady_state + [
            [FRA, AMY, MAR],
        ])
    def test_powerless_waives(self):
        ''' Builds can be waived without specifying your power'''
        steady_state = [
            [FRA, AMY, PAR],
        ]
        self.init_state(WIN, 1901, steady_state)
        self.legalOrder(FRA, [WVE])
        self.legalOrder(FRA, [(FRA, AMY, MAR), BLD])
        self.illegalOrder(FRA, [(FRA, AMY, BRE), BLD])
        self.assertMapState(steady_state + [
            [FRA, AMY, MAR],
        ])
    def test_retreat_into_mover(self):
        ''' A unit cannot retreat into a province someone else moved into.'''
        steady_state = [
            [TUR, FLT, BLA],
        ]
        self.init_state(SPR, 1901, steady_state + [
            [TUR, AMY, SEV],
            [AUS, AMY, RUM],
            [RUS, AMY, WAR],
        ])
        self.legalOrder(TUR, [(TUR, FLT, BLA), SUP, (TUR, AMY, SEV), MTO, RUM])
        self.legalOrder(TUR, [(TUR, AMY, SEV), MTO, RUM])
        self.legalOrder(AUS, [(AUS, AMY, RUM), HLD])
        self.legalOrder(RUS, [(RUS, AMY, WAR), MTO, UKR])
        new_state = steady_state + [
            [TUR, AMY, RUM],
            [RUS, AMY, UKR],
        ]
        self.assertMapState(new_state + [
            [AUS, AMY, RUM, MRT],
        ])
        self.illegalOrder(AUS, [(AUS, AMY, RUM), RTO, UKR])
        self.assertMapState(new_state)
    
    def retract(self, country, order):
        client = self.Fake_Service(country)
        message = NOT(SUB(order))
        self.judge.handle_NOT_SUB(client, message)
        self.assertContains(client.replies, YES(message))
    def test_retracting_new_order(self):
        ''' Retracting a newer order should re-instate the old order.'''
        self.init_state(SPR, 1902, [
                [GER, AMY, RUH],
        ])
        self.legalOrder(GER, [(GER, AMY, RUH), MTO, BUR])
        self.legalOrder(GER, [(GER, AMY, RUH), MTO, BEL])
        self.retract(   GER, [(GER, AMY, RUH), MTO, BEL])
        self.assertMapState([
                [GER, AMY, BUR],
        ])
    def test_retracting_old_order(self):
        ''' Retracting an older order should keep the new order.'''
        self.init_state(SPR, 1902, [
                [GER, AMY, RUH],
        ])
        self.legalOrder(GER, [(GER, AMY, RUH), MTO, BUR])
        self.legalOrder(GER, [(GER, AMY, RUH), MTO, BEL])
        self.retract(   GER, [(GER, AMY, RUH), MTO, BUR])
        self.assertMapState([
                [GER, AMY, BEL],
        ])
    def test_retracting_only_order(self):
        ''' Retracting a unit's only order should leave it unordered.'''
        self.init_state(SPR, 1902, [
                [GER, AMY, RUH],
        ])
        self.legalOrder(GER, [(GER, AMY, RUH), MTO, BEL])
        self.retract(   GER, [(GER, AMY, RUH), MTO, BEL])
        self.assertMapState([
                [GER, AMY, RUH],
        ])

class Judge_Loose(DiplomacyAdjudicatorTestCase):
    ''' Judge output for loose orders'''
    game_options = {
        'send_ORD': True,
        'AOA': False,
    }
    
    def assertOrdered(self, order):
        orders = [msg for msg in self.results if msg[0] is ORD]
        self.assertContains(orders, order)
    
    # (power unit_type province) MTO province
    def test_ordered_power_type_province(self):
        ''' An omitted coast in the unit specification will be filled in.'''
        self.init_state(FAL, 1901, [
            [FRA, FLT, [SPA, NCS]],
        ])
        self.legalOrder(FRA, [(FRA, FLT, SPA), MTO, MAO])
        self.assertMapState([
            [FRA, FLT, MAO],
        ])
        self.assertOrdered(ORD (FAL, 1901)
            ([FRA, FLT, (SPA, NCS)], MTO, MAO) (SUC))
    
    # (power unit_type (province coast)) MTO province
    def test_ordered_power_type_province_coast(self):
        ''' A coast can be specified in the unit specification of an order.'''
        self.init_state(FAL, 1901, [
            [FRA, FLT, [SPA, NCS]],
        ])
        self.legalOrder(FRA, [(FRA, FLT, [SPA, NCS]), MTO, MAO])
        self.assertMapState([
            [FRA, FLT, MAO],
        ])
        self.assertOrdered(ORD (FAL, 1901)
            ([FRA, FLT, (SPA, NCS)], MTO, MAO) (SUC))
    
    # province MTO province
    def test_ordered_province(self):
        ''' An ordered unit can be specified by only its province.'''
        self.init_state(FAL, 1901, [
            [FRA, FLT, [SPA, NCS]],
        ])
        self.legalOrder(FRA, [SPA, MTO, MAO])
        self.assertMapState([
            [FRA, FLT, MAO],
        ])
        self.assertOrdered(ORD (FAL, 1901)
            ([FRA, FLT, (SPA, NCS)], MTO, MAO) (SUC))
    
    # (province) MTO province
    def test_ordered_province_bracketed(self):
        ''' An ordered unit can be specified by only a province in brackets.'''
        self.init_state(FAL, 1901, [
            [FRA, FLT, [SPA, NCS]],
        ])
        self.legalOrder(FRA, [[SPA], MTO, MAO])
        self.assertMapState([
            [FRA, FLT, MAO],
        ])
        self.assertOrdered(ORD (FAL, 1901)
            ([FRA, FLT, (SPA, NCS)], MTO, MAO) (SUC))
    
    # ((province coast)) MTO province
    # (power province) MTO province
    # (power (province coast)) MTO province
    # (unit_type province) MTO province
    # (unit_type (province coast)) MTO province
    
    # (unit) SUP (power unit_type province)
    # (unit) SUP (power unit_type (province coast))
    # (unit) SUP province
    # (unit) SUP (province)
    # (unit) SUP ((province coast))
    # (unit) SUP (power province)
    # (unit) SUP (power (province coast))
    # (unit) SUP (unit_type province)
    # (unit) SUP (unit_type (province coast))
    
    # (unit) MTO province --> MTO (province coast)
    def test_destination_coastless(self):
        ''' An omitted destination coast will be filled in.'''
        self.judge.datc.datc_4b2 = 'a'
        self.init_state(FAL, 1901, [
            [FRA, FLT, GAS],
        ])
        self.legalOrder(FRA, [(FRA, FLT, GAS), MTO, SPA])
        self.assertMapState([
            [FRA, FLT, [SPA, NCS]],
        ])
        self.assertOrdered(ORD (FAL, 1901)
            ([FRA, FLT, GAS], MTO, [SPA, NCS]) (SUC))
    
    # (unit) SUP (unit) MTO province
    # (unit) SUP (unit) MTO (province coast)
    # (unit) SUP (unit) CTO province
    def test_convoy_pathless(self):
        self.judge.datc.datc_4a6 = 'b'
        self.init_state(SPR, 1901, [
            [ENG, AMY, EDI],
            [ENG, FLT, NWG],
        ])
        self.legalOrder(ENG, [(ENG, AMY, EDI), CTO, NWY])
        self.legalOrder(ENG, [(ENG, FLT, NWG), CVY, (ENG, AMY, EDI), CTO, NWY])
        self.assertMapState([
            [ENG, AMY, NWY],
            [ENG, FLT, NWG],
        ])
        self.assertOrdered(ORD (SPR, 1901)
            ([ENG, AMY, EDI], CTO, NWY, VIA, [NWG]) (SUC))
    
    # (unit) SUP (unit) CTO province VIA (province province ...)
    # (unit) CVY (unit) CTO province VIA (province province ...)
    
    # (unit) CTO (province coast)
    def test_convoy_coast(self):
        ''' An army can be convoyed to a specific coast.'''
        self.judge.datc.datc_4b6 = 'b'
        self.init_state(FAL, 1901, [
            [RUS, AMY, SWE],
            [RUS, FLT, GOB],
        ])
        self.legalOrder(RUS, [(RUS, AMY, SWE), CTO, (STP, SCS), VIA, [GOB]])
        self.legalOrder(RUS,
            [(RUS, FLT, GOB), CVY, (RUS, AMY, SWE), CTO, (STP, SCS)])
        self.assertMapState([
            [RUS, AMY, STP],
            [RUS, FLT, GOB],
        ])
        self.assertOrdered(ORD (FAL, 1901)
            ([RUS, AMY, SWE], CTO, STP, VIA, [GOB]) (SUC))
        self.assertOrdered(ORD (FAL, 1901)
            ([RUS, FLT, GOB], CVY, [RUS, AMY, SWE], CTO, STP) (SUC))
    def test_convoyed_coast(self):
        ''' An army can attempt to be convoyed to a specific coast.'''
        self.judge.datc.datc_4b6 = 'b'
        self.init_state(FAL, 1901, [
            [RUS, AMY, SWE],
            [RUS, FLT, GOB],
        ])
        self.legalOrder(RUS, [(RUS, AMY, SWE), CTO, (STP, SCS), VIA, [GOB]])
        self.legalOrder(RUS, [(RUS, FLT, GOB), CVY, (RUS, AMY, SWE), CTO, STP])
        self.assertMapState([
            [RUS, AMY, STP],
            [RUS, FLT, GOB],
        ])
        self.assertOrdered(ORD (FAL, 1901)
            ([RUS, AMY, SWE], CTO, STP, VIA, [GOB]) (SUC))
    def test_convoying_coast(self):
        ''' A fleet can attempt to convoy an army to a specific coast.'''
        self.judge.datc.datc_4b6 = 'b'
        self.init_state(FAL, 1901, [
            [RUS, AMY, SWE],
            [RUS, FLT, GOB],
        ])
        self.legalOrder(RUS, [(RUS, AMY, SWE), CTO, STP, VIA, [GOB]])
        self.legalOrder(RUS,
            [(RUS, FLT, GOB), CVY, (RUS, AMY, SWE), CTO, (STP, SCS)])
        self.assertMapState([
            [RUS, AMY, STP],
            [RUS, FLT, GOB],
        ])
        self.assertOrdered(ORD (FAL, 1901)
            ([RUS, FLT, GOB], CVY, [RUS, AMY, SWE], CTO, STP) (SUC))
    
    # VIA when both undisrupted
    # VIA when one disrupted
    # VIA when the other undisrupted
    # VIA when both disrupted
    # VIA when no route available
    
    # Retreat phase orders:
    # (unit) RTO province --> RTO (province coast)
    
    # Build phase orders:
    # province BLD --> (power AMY province) BLD
    # (FLT province) BLD --> (power FLT province) BLD
    # WVE --> power WVE

class Judge_Doctests(unittest.TestCase):
    ''' Tests that were once in doctest format.'''
    
    def test_startup(self):
        variant = variants['standard']
        judge = variant.new_judge(GameOptions())
        messages = judge.start()
        self.failUnlessEqual([msg[0] for msg in messages], [SCO, NOW])
        self.failUnlessEqual(judge.phase, 0x20)
    def test_attack_calculation(self):
        Rome = standard_map.locs[(AMY, ROM, None)]
        Venice = standard_map.locs[(AMY, VEN, None)]
        Trieste = standard_map.locs[(AMY, TRI, None)]
        Rome.province.entering = []
        
        Rome_unit = Rome.province.units[0]
        Venice_unit = Venice.province.units[0]
        Rome_unit.decisions = {}
        Venice_unit.decisions = {}
        Rome_unit.supports = []
        
        Rome_order = MoveOrder(Rome_unit, Venice)
        Venice_order = MoveOrder(Venice_unit, Trieste)
        move = Move_Decision(Venice_order)
        path = Path_Decision(Rome_order, None, False, False)
        move.passed = True
        path.passed = True
        
        choice = Attack_Decision(Rome_order)
        choice.init_deps()
        self.assertEqual(choice.depends, [path, move])
        self.failUnless(choice.calculate())
        self.failUnlessEqual(choice.min_value, 1)
        self.failUnlessEqual(choice.max_value, 1)
    def test_move_calculation(self):
        Vienna = standard_map.locs[(AMY, VIE, None)]
        Galicia = standard_map.locs[(AMY, GAL, None)]
        Warsaw = standard_map.locs[(AMY, WAR, None)]
        Vienna.province.entering = []
        
        Vienna_unit = Vienna.province.units[0]
        Warsaw_unit = Warsaw.province.units[0]
        Vienna_unit.decisions = {}
        Warsaw_unit.decisions = {}
        #Vienna_unit.supports = []
        
        Vienna_order = MoveOrder(Vienna_unit, Galicia)
        Warsaw_order = MoveOrder(Warsaw_unit, Galicia)
        attack = Attack_Decision(Vienna_order)
        attack.min_value = attack.max_value = 1
        prevent = Prevent_Decision(Warsaw_order)
        prevent.min_value = prevent.max_value = 1
        
        Galicia.province.hold = hold = Hold_Decision(None)
        hold.min_value = hold.max_value = 0
        Galicia.province.entering = [Warsaw_unit, Vienna_unit]
        choice = Move_Decision(Vienna_order)
        choice.init_deps()
        
        self.assertEqual(choice.depends, [attack, hold, prevent])
        self.failUnless(choice.calculate())
        self.failUnless(choice.failed)
        self.failIf(choice.passed)

class Judge_Bugfix(DiplomacyAdjudicatorTestCase):
    ''' Test cases to reproduce bugs that have been fixed.'''
    game_options = {'send_ORD': True}
    
    def test_orderless_convoyee(self):
        'Error when convoying an army without an order'
        self.judge.datc.datc_4a3 = 'f'
        steady_state = [
            [TUR, FLT, BLA],
            [TUR, AMY, ANK],
        ]
        self.init_state(SPR, 1901, steady_state)
        self.legalOrder(TUR, [(TUR, FLT, BLA), CVY, (TUR, AMY, ANK), CTO, SEV])
        self.assertMapState(steady_state)
    def test_retreat_past_attacker_full(self):
        ''' Bug caused by checking a dislodger's province after moving it.'''
        steady_state = [
            [TUR, FLT, BLA],
            [TUR, FLT, CON],
            [TUR, AMY, SMY],
            [TUR, AMY, ANK],
            [AUS, FLT, VEN],
            [AUS, AMY, TRI],
            [AUS, AMY, SER],
            [AUS, AMY, BUL],
            [AUS, AMY, BUD],
            [ENG, FLT, DEN],
            [ENG, AMY, RUH],
            [ENG, FLT, ECH],
            [ENG, FLT, NWY],
            [ENG, FLT, WAL],
            [ITA, FLT, AEG],
            [ITA, AMY, VIE],
            [ITA, FLT, GRE],
            [ITA, AMY, NAP],
            [ITA, AMY, ROM],
            [RUS, AMY, UKR],
            [RUS, AMY, GAL],
            [RUS, AMY, SWE],
            [RUS, AMY, MOS],
            [FRA, AMY, PAR],
            [FRA, AMY, MAR],
        ]
        self.init_state(SPR, 1901, steady_state + [
            [TUR, FLT, MAO],
            [TUR, AMY, SEV],
            [AUS, AMY, RUM],
            [ENG, FLT, BEL],
            [ENG, FLT, NTH],
            [ENG, FLT, LON],
            [ITA, AMY, HOL],
            [GER, AMY, BER],
        ])
        self.legalOrder(TUR, [(TUR, FLT, BLA), SUP, (TUR, AMY, SEV), MTO, RUM])
        self.legalOrder(TUR, [(TUR, FLT, MAO), MTO, BRE])
        self.legalOrder(TUR, [(TUR, FLT, CON), SUP, (TUR, AMY, SMY)])
        self.legalOrder(TUR, [(TUR, AMY, SMY), SUP, (TUR, FLT, CON)])
        self.legalOrder(TUR, [(TUR, AMY, SEV), MTO, RUM])
        self.legalOrder(TUR, [(TUR, AMY, ANK), SUP, (TUR, FLT, CON)])
        self.legalOrder(AUS, [(AUS, FLT, VEN), SUP, (AUS, AMY, TRI)])
        self.legalOrder(AUS, [(AUS, AMY, TRI), SUP, (AUS, AMY, BUD)])
        self.legalOrder(AUS, [(AUS, AMY, SER), MTO, GRE])
        self.legalOrder(AUS, [(AUS, AMY, BUL), MTO, CON])
        self.legalOrder(AUS, [(AUS, AMY, BUD), SUP, (AUS, AMY, RUM)])
        self.legalOrder(AUS, [(AUS, AMY, RUM), SUP, (AUS, AMY, BUD)])
        self.legalOrder(ENG, [(ENG, FLT, BEL), MTO, HOL])
        self.legalOrder(ENG, [(ENG, FLT, DEN), SUP, (ENG, FLT, LON), MTO, NTH])
        self.legalOrder(ENG, [(ENG, AMY, RUH), SUP, (ENG, FLT, BEL), MTO, HOL])
        self.legalOrder(ENG, [(ENG, FLT, ECH), SUP, (ENG, FLT, NTH), MTO, BEL])
        self.legalOrder(ENG, [(ENG, FLT, NTH), MTO, BEL])
        self.legalOrder(ENG, [(ENG, FLT, NWY), MTO, (STP, NCS)])
        self.legalOrder(ENG, [(ENG, FLT, WAL), SUP, (ENG, FLT, ECH)])
        self.legalOrder(ENG, [(ENG, FLT, LON), MTO, NTH])
        self.legalOrder(ITA, [(ITA, FLT, AEG), MTO, CON])
        self.legalOrder(ITA, [(ITA, AMY, VIE), MTO, BUD])
        self.legalOrder(ITA, [(ITA, AMY, HOL), MTO, KIE])
        self.legalOrder(ITA, [(ITA, FLT, GRE), HLD])
        self.legalOrder(ITA, [(ITA, AMY, NAP), HLD])
        self.legalOrder(ITA, [(ITA, AMY, ROM), MTO, VEN])
        self.legalOrder(RUS, [(RUS, AMY, UKR), MTO, MOS])
        self.legalOrder(RUS, [(RUS, AMY, GAL), MTO, VIE])
        self.legalOrder(RUS, [(RUS, AMY, SWE), MTO, DEN])
        self.legalOrder(RUS, [(RUS, AMY, MOS), MTO, STP])
        self.legalOrder(GER, [(GER, AMY, BER), MTO, MUN])
        self.legalOrder(FRA, [(FRA, AMY, PAR), HLD])
        self.legalOrder(FRA, [(FRA, AMY, MAR), HLD])
        
        new_state = steady_state + [
            [TUR, FLT, BRE],
            [TUR, AMY, RUM],
            [ENG, FLT, HOL],
            [ENG, FLT, BEL],
            [ENG, FLT, NTH],
            [ITA, AMY, KIE],
            [GER, AMY, MUN],
        ]
        self.assertMapState(new_state + [
            [AUS, AMY, RUM, MRT],
        ])
        self.illegalOrder(AUS, [(AUS, AMY, RUM), RTO, SEV])
        self.assertMapState(new_state)
    def test_retreat_past_attacker_simple(self):
        ''' Condensed version of the problem above'''
        steady_state = [
            [TUR, FLT, BLA],
        ]
        self.init_state(SPR, 1901, steady_state + [
            [TUR, AMY, SEV],
            [AUS, AMY, RUM],
        ])
        self.legalOrder(TUR, [(TUR, FLT, BLA), SUP, (TUR, AMY, SEV), MTO, RUM])
        self.legalOrder(TUR, [(TUR, AMY, SEV), MTO, RUM])
        self.legalOrder(AUS, [(AUS, AMY, RUM), HLD])
        new_state = steady_state + [
            [TUR, AMY, RUM],
        ]
        self.assertMapState(new_state + [
            [AUS, AMY, RUM, MRT],
        ])
        self.illegalOrder(AUS, [(AUS, AMY, RUM), RTO, SEV])
        self.assertMapState(new_state)
    def test_empty_nation_error(self):
        ''' An error occurred when processing orders for doubled units.
            This shouldn't happen anyway, but it's worth fixing.
            It currently flags the order as NSU; should it instead be legal?
        '''#'''
        self.init_state(SPR, 1901, [
            [TUR, FLT, BLA],
            [TUR, AMY, SEV],
            [TUR, AMY, SEV],
        ])
        self.illegalOrder(TUR, [(TUR, FLT, BLA), SUP, (TUR, AMY, SEV), MTO, RUM])
    def test_removing_last_units_error(self):
        ''' The judge used to reject REM orders from just-eliminated countries.
            They get removed anyway, but only when time runs out.
            Fixed by allowing any eliminated country to submit orders,
            relying on other processing to reject any invalid orders.
        '''#'''
        steady_state = [
            [RUS, AMY, BER],
            [RUS, AMY, MUN],
            [RUS, AMY, KIE],
        ]
        start_state = steady_state + [
            [GER, FLT, NTH],
        ]
        self.init_state(FAL, 1901, start_state)
        self.assertMapState(start_state)
        self.legalOrder(GER, [(GER, FLT, NTH), REM])
        self.assertMapState(steady_state)
    def test_retracting_order_error(self):
        ''' The server crashed when I attempted to retract an order.'''
        self.init_state(SPR, 1902, [ [GER, AMY, RUH], ])
        client = self.Fake_Service(GER)
        self.judge.handle_NOT_SUB(client, NOT(SUB([GER, AMY, RUH], MTO, BEL)))
    def test_void_convoying_order_result_success(self):
        ''' CVY orders always had NSO results, even for successful convoys.'''
        steady_state = [
            [ENG, FLT, NTH],
        ]
        self.init_state(FAL, 1901, steady_state + [
            [ENG, AMY, YOR],
        ])
        self.legalOrder(ENG, [(ENG, FLT, NTH), CVY, (ENG, AMY, YOR), CTO, NWY])
        self.legalOrder(ENG, [(ENG, AMY, YOR), CTO, NWY, VIA, [NTH]])
        self.assertMapState(steady_state + [
            [ENG, AMY, NWY],
        ])
        self.assertContains(self.results, ORD(FAL, 1901)
            ([ENG, FLT, NTH], CVY, [ENG, AMY, YOR], CTO, NWY) (SUC))
    def test_void_convoying_order_result_bounce(self):
        ''' CVY orders shouldn't get BNC results, even if the convoy bounces.'''
        steady_state = [
            [RUS, FLT, GOB],
            [RUS, AMY, STP],
            [GER, AMY, DEN],
        ]
        self.init_state(SPR, 1902, steady_state)
        self.legalOrder(RUS, [(RUS, FLT, GOB), CVY, (RUS, AMY, STP), CTO, SWE])
        self.legalOrder(RUS, [(RUS, AMY, STP), CTO, SWE, VIA, [GOB]])
        self.legalOrder(GER, [(GER, AMY, DEN), MTO, SWE])
        self.assertMapState(steady_state)
        self.assertContains(self.results, ORD(SPR, 1902)
            ([RUS, FLT, GOB], CVY, [RUS, AMY, STP], CTO, SWE) (SUC))
        self.assertContains(self.results, ORD(SPR, 1902)
            ([RUS, AMY, STP], CTO, SWE, VIA, [GOB]) (BNC))
    def test_void_convoying_order_result_retreat(self):
        ''' CVY orders shouldn't get DSR results, even if disrupted.'''
        self.init_state(SPR, 1902, [
            [ENG, FLT, NTH],
            [ENG, FLT, SKA],
            [ENG, AMY, YOR],
            [FRA, FLT, BEL],
            [FRA, FLT, HOL],
        ])
        self.legalOrder(ENG, [(ENG, FLT, NTH), CVY, (ENG, AMY, YOR), CTO, SWE])
        self.legalOrder(ENG, [(ENG, FLT, SKA), CVY, (ENG, AMY, YOR), CTO, SWE])
        self.legalOrder(ENG, [(ENG, AMY, YOR), CTO, SWE, VIA, [NTH, SKA]])
        self.legalOrder(FRA, [(FRA, FLT, BEL), MTO, NTH])
        self.legalOrder(FRA, [(FRA, FLT, HOL), SUP, (FRA, FLT, BEL), MTO, NTH])
        self.assertMapState([
            [ENG, FLT, NTH, MRT],
            [ENG, FLT, SKA],
            [ENG, AMY, YOR],
            [FRA, FLT, NTH],
            [FRA, FLT, HOL],
        ])
        self.assertContains(self.results, ORD(SPR, 1902)
            ([ENG, FLT, NTH], CVY, [ENG, AMY, YOR], CTO, SWE) (RET))
        self.assertContains(self.results, ORD(SPR, 1902)
            ([ENG, FLT, SKA], CVY, [ENG, AMY, YOR], CTO, SWE) (SUC))
        self.assertContains(self.results, ORD(SPR, 1902)
            ((ENG, AMY, YOR), CTO, SWE, VIA, [NTH, SKA]) (DSR))
    def test_matches_support_missing_unit_move(self):
        # A support to move from an empty province never matches an order set.
        order = [(GER, AMY, KIE), SUP, (GER, AMY, RUH), MTO, HOL]
        support = createUnitOrder(order, GER, standard_map, self.judge.datc)
        result = support.matches(OrderSet())
        self.assertEqual(result, False)
    
    def test_unconvoyed_support_cut(self):
        # Denmark's support should be marked as uncut in this situation,
        # according to page 16 of the 2000 rules.
        # Unfortunately, Parlance still reports it as cut,
        # because it doesn't affect the adjudication.
        self.judge.datc.datc_4a2 = 'd'
        orders = [
            ([(FRA, AMY, BRE), MTO, GAS], SUC),
            ([(FRA, AMY, BUR), MTO, RUH], SUC),
            ([(FRA, AMY, HOL), SUP, (FRA, AMY, BUR), MTO, RUH], CUT),
            ([(FRA, AMY, PAR), MTO, BUR], SUC),
            ([(FRA, AMY, PIC), SUP, (FRA, AMY, PAR), MTO, BUR], SUC),
            ([(FRA, AMY, YOR), CTO, DEN, VIA, [NTH]], BNC),
            ([(FRA, FLT, BEL), SUP, (FRA, FLT, NTH)], SUC),
            ([(FRA, FLT, EDI), SUP, (FRA, FLT, NTH)], SUC),
            ([(FRA, FLT, NTH), CVY, (FRA, AMY, YOR), CTO, DEN], SUC),
            ([(FRA, FLT, SWE), SUP, (FRA, AMY, YOR), MTO, DEN], CUT),
            ([(GER, AMY, BOH), MTO, MUN], BNC),
            ([(GER, AMY, GAL), MTO, SIL], SUC),
            ([(GER, AMY, MAR), MTO, SPA], SUC),
            ([(GER, AMY, MUN), MTO, BUR], BNC),
            ([(GER, AMY, UKR), MTO, GAL], SUC),
            ([(GER, FLT, DEN), SUP, (GER, FLT, HEL), MTO, NTH], CUT),
            ([(GER, FLT, HEL), MTO, NTH], BNC),
            ([(GER, FLT, KIE), MTO, HOL], BNC),
            ([(GER, FLT, NWG), SUP, (GER, FLT, HEL), MTO, NTH], SUC),
            ([(GER, FLT, NWY), MTO, SWE], BNC),
            ([(ITA, AMY, NAP), SUP, (ITA, AMY, VEN), MTO, ROM], SUC),
            ([(ITA, AMY, VEN), MTO, ROM], SUC),
            ([(ITA, FLT, ION), MTO, AEG], BNC),
            ([(TUR, AMY, ALB), MTO, TRI], SUC),
            ([(TUR, AMY, BUL), MTO, SER], SUC),
            ([(TUR, AMY, GRE), SUP, (TUR, AMY, SER), MTO, ALB], SUC),
            ([(TUR, AMY, SER), MTO, ALB], SUC),
            ([(TUR, AMY, SMY), MTO, SYR], SUC),
            ([(TUR, AMY, TRI), MTO, VEN], SUC),
            ([(TUR, AMY, TYR), SUP, (TUR, AMY, TRI), MTO, VEN], SUC),
            ([(TUR, FLT, AEG), MTO, ION], BNC),
            ([(TUR, FLT, ANK), HLD], SUC),
            ([(TUR, FLT, CON), MTO, AEG], BNC),
            ([(TUR, FLT, ROM), MTO, NAP], [BNC, RET]),
        ]
        
        self.init_state(SPR, 1917, [order[0][0] for order in orders])
        
        for order, result in orders:
            self.legalOrder(order[0][0], order)
        
        self.assertMapState([
            [FRA, AMY, BUR],
            [FRA, AMY, GAS],
            [FRA, AMY, HOL],
            [FRA, AMY, PIC],
            [FRA, AMY, RUH],
            [FRA, AMY, YOR],
            [FRA, FLT, BEL],
            [FRA, FLT, EDI],
            [FRA, FLT, NTH],
            [FRA, FLT, SWE],
            [GER, AMY, BOH],
            [GER, AMY, GAL],
            [GER, AMY, MUN],
            [GER, AMY, SIL],
            [GER, AMY, SPA],
            [GER, FLT, DEN],
            [GER, FLT, HEL],
            [GER, FLT, KIE],
            [GER, FLT, NWG],
            [GER, FLT, NWY],
            [ITA, AMY, NAP],
            [ITA, AMY, ROM],
            [ITA, FLT, ION],
            [TUR, AMY, ALB],
            [TUR, AMY, GRE],
            [TUR, AMY, SER],
            [TUR, AMY, SYR],
            [TUR, AMY, TRI],
            [TUR, AMY, TYR],
            [TUR, AMY, VEN],
            [TUR, FLT, AEG],
            [TUR, FLT, ANK],
            [TUR, FLT, CON],
            [TUR, FLT, ROM, MRT],
        ])
        
        for order, result in orders:
            self.assertContains(self.results, ORD (SPR, 1917) (order) (result))
    def test_unconvoyed_support_uncut(self):
        # Denmark's support should be marked as uncut in this situation,
        # due to the 1982 paradox-resolution rule.
        # It doesn't affect the adjudication here, though.
        self.judge.datc.datc_4a2 = 'b'
        orders = [
            ([(FRA, AMY, BRE), MTO, GAS], SUC),
            ([(FRA, AMY, BUR), MTO, RUH], SUC),
            ([(FRA, AMY, HOL), SUP, (FRA, AMY, BUR), MTO, RUH], CUT),
            ([(FRA, AMY, PAR), MTO, BUR], SUC),
            ([(FRA, AMY, PIC), SUP, (FRA, AMY, PAR), MTO, BUR], SUC),
            ([(FRA, AMY, YOR), CTO, DEN, VIA, [NTH]], BNC),
            ([(FRA, FLT, BEL), SUP, (FRA, FLT, NTH)], SUC),
            ([(FRA, FLT, EDI), SUP, (FRA, FLT, NTH)], SUC),
            ([(FRA, FLT, NTH), CVY, (FRA, AMY, YOR), CTO, DEN], SUC),
            ([(FRA, FLT, SWE), SUP, (FRA, AMY, YOR), MTO, DEN], CUT),
            ([(GER, AMY, BOH), MTO, MUN], BNC),
            ([(GER, AMY, GAL), MTO, SIL], SUC),
            ([(GER, AMY, MAR), MTO, SPA], SUC),
            ([(GER, AMY, MUN), MTO, BUR], BNC),
            ([(GER, AMY, UKR), MTO, GAL], SUC),
            ([(GER, FLT, DEN), SUP, (GER, FLT, HEL), MTO, NTH], SUC),
            ([(GER, FLT, HEL), MTO, NTH], BNC),
            ([(GER, FLT, KIE), MTO, HOL], BNC),
            ([(GER, FLT, NWG), SUP, (GER, FLT, HEL), MTO, NTH], SUC),
            ([(GER, FLT, NWY), MTO, SWE], BNC),
            ([(ITA, AMY, NAP), SUP, (ITA, AMY, VEN), MTO, ROM], SUC),
            ([(ITA, AMY, VEN), MTO, ROM], SUC),
            ([(ITA, FLT, ION), MTO, AEG], BNC),
            ([(TUR, AMY, ALB), MTO, TRI], SUC),
            ([(TUR, AMY, BUL), MTO, SER], SUC),
            ([(TUR, AMY, GRE), SUP, (TUR, AMY, SER), MTO, ALB], SUC),
            ([(TUR, AMY, SER), MTO, ALB], SUC),
            ([(TUR, AMY, SMY), MTO, SYR], SUC),
            ([(TUR, AMY, TRI), MTO, VEN], SUC),
            ([(TUR, AMY, TYR), SUP, (TUR, AMY, TRI), MTO, VEN], SUC),
            ([(TUR, FLT, AEG), MTO, ION], BNC),
            ([(TUR, FLT, ANK), HLD], SUC),
            ([(TUR, FLT, CON), MTO, AEG], BNC),
            ([(TUR, FLT, ROM), MTO, NAP], [BNC, RET]),
        ]
        
        self.init_state(SPR, 1917, [order[0][0] for order in orders])
        
        for order, result in orders:
            self.legalOrder(order[0][0], order)
        
        self.assertMapState([
            [FRA, AMY, BUR],
            [FRA, AMY, GAS],
            [FRA, AMY, HOL],
            [FRA, AMY, PIC],
            [FRA, AMY, RUH],
            [FRA, AMY, YOR],
            [FRA, FLT, BEL],
            [FRA, FLT, EDI],
            [FRA, FLT, NTH],
            [FRA, FLT, SWE],
            [GER, AMY, BOH],
            [GER, AMY, GAL],
            [GER, AMY, MUN],
            [GER, AMY, SIL],
            [GER, AMY, SPA],
            [GER, FLT, DEN],
            [GER, FLT, HEL],
            [GER, FLT, KIE],
            [GER, FLT, NWG],
            [GER, FLT, NWY],
            [ITA, AMY, NAP],
            [ITA, AMY, ROM],
            [ITA, FLT, ION],
            [TUR, AMY, ALB],
            [TUR, AMY, GRE],
            [TUR, AMY, SER],
            [TUR, AMY, SYR],
            [TUR, AMY, TRI],
            [TUR, AMY, TYR],
            [TUR, AMY, VEN],
            [TUR, FLT, AEG],
            [TUR, FLT, ANK],
            [TUR, FLT, CON],
            [TUR, FLT, ROM, MRT],
        ])
        
        for order, result in orders:
            self.assertContains(self.results, ORD (SPR, 1917) (order) (result))

class Judge_Americas(DiplomacyAdjudicatorTestCase):
    ''' Fixing bugs in the Americas4 map variant.'''
    variant_name = 'americas4'
    @timed(10)
    def test_convoy_problem(self):
        ''' This situation started chewing up memory and CPU like mad.'''
        rep = self.judge.map.variant.rep
        now = rep.translate('''NOW ( FAL 1848 )
                ( MXC AMY ORE ) ( MXC FLT COM ) ( MXC FLT MPO )
                ( MXC FLT NPO ) ( MXC FLT WCB )
        ''') #'''
        sub = rep.translate('''SUB
                ( ( MXC FLT WCB ) MTO ( NIC ECS ) )
                ( ( MXC FLT NPO ) CVY ( MXC AMY ORE ) CTO ALA )
                ( ( MXC FLT COM ) MTO GOT )
                ( ( MXC AMY ORE ) CTO ALA VIA ( NPO ) )
                ( ( MXC FLT MPO ) MTO GAL )
        ''') #'''
        self.judge.map.handle_NOW(now)
        self.judge.init_turn()
        client = self.Fake_Service(rep['MXC'])
        self.judge.handle_SUB(client, sub)

class Judge_Notes(DiplomacyAdjudicatorTestCase):
    ''' Order notes given for erroneous orders:
        - MBV: Order is OK
        - FAR: Not adjacent
        - NSP: No such province
        - NSU: No such unit
        - NAS: Not at sea (for a convoying fleet)
        - NSF: No such fleet (in VIA section of CTO
               or the unit performing a CVY)
        - NSA: No such army (for unit being ordered to CTO
               or for unit being CVYed)
        - NYU: Not your unit
        - NRN: No retreat needed for this unit
        - NVR: Not a valid retreat space
        - YSC: Not your supply centre
        - ESC: Not an empty supply centre
        - HSC: Not a home supply centre
        - NSC: Not a supply centre
        - CST: No coast specified for fleet build in bicoastal province,
               or an attempt to build a fleet inland, or an army at sea.
        - NMB: No more builds allowed
        - NMR: No more removals allowed
        - NRS: Not the right season
    '''#'''
    def assertOrderNote(self, country, order, note):
        result = self.submitOrder(country, order)
        self.failUnlessEqual(result, note)
    
    # HoldOrder notes
    # RetreatOrder notes
    # DisbandOrder notes
    # RemoveOrder notes
    # WaiveOrder notes
    
    # MoveOrder notes
    def test_far_impossible_move(self):
        ''' FAR for movement to non-adjacent province'''
        self.assertOrderNote(ENG, [(ENG, FLT, LON), MTO, NWY], FAR)
    def test_far_inland(self):
        ''' FAR for fleet movement to inland province'''
        self.assertOrderNote(RUS, [(RUS, FLT, SEV), MTO, UKR], FAR)
    def test_far_sea(self):
        ''' FAR for army movement to sea province'''
        self.assertOrderNote(FRA, [(FRA, AMY, MAR), MTO, GOL], FAR)
    def test_far_wrong_coast(self):
        ''' FAR for fleet movement to a non-adjacent coastline'''
        self.init_state(SPR, 1901, [ (TUR, FLT, BLA) ])
        self.assertOrderNote(TUR, [(TUR, FLT, BLA), MTO, (BUL, SCS)], FAR)
    
    # ConvoyedOrder notes
    def test_far_impossible_convoy(self):
        ''' FAR for an army convoyed with no possible convoy route'''
        self.assertOrderNote(GER, [(GER, AMY, BER), CTO, HOL], FAR)
    def test_far_fleetless_convoy(self):
        ''' FAR for an army convoyed with a missing convoy fleet.
            Todo: This should probably be changed to NSF.
        '''#'''
        self.init_state(SPR, 1901, [
            [ENG, AMY, NWY],
            [ENG, FLT, NTH],
        ])
        self.assertOrderNote(ENG, [(ENG, AMY, NWY), CTO, KIE, VIA, [NTH, HEL]], FAR)
    def test_far_doubled_convoy(self):
        ''' FAR for convoying an army twice through a sea'''
        self.init_state(SPR, 1901, [
            [ENG, AMY, DEN],
            [ENG, FLT, NTH],
            [ENG, FLT, NWG],
            [ENG, FLT, NAO],
            [ENG, FLT, IRI],
            [ENG, FLT, ECH],
        ])
        self.assertOrderNote(ENG, [(ENG, AMY, DEN), CTO, HOL, VIA, [NTH, NWG, NAO, IRI, ECH, NTH]], FAR)
    def test_far_inland_convoy(self):
        ''' FAR for convoying an army through a land province.
            This might want to be changed to NSF, maybe.
        '''#'''
        self.init_state(SPR, 1901, [
            [AUS, AMY, GRE],
            [AUS, AMY, SER],
        ])
        self.assertOrderNote(AUS, [(AUS, AMY, GRE), CTO, TRI, VIA, [SER]], FAR)
    def test_cst_convoyed_coast(self):
        ''' CST for attempting to be convoyed to a specific coast.'''
        self.judge.datc.datc_4b6 = 'a'
        self.init_state(FAL, 1901, [
            [RUS, AMY, SWE],
            [RUS, FLT, GOB],
        ])
        self.assertOrderNote(RUS,
            [(RUS, AMY, SWE), CTO, (STP, SCS), VIA, [GOB]], CST)
    
    # SupportOrder notes
    def test_far_support_hold(self):
        ''' FAR for supporting a hold in a non-adjacent province'''
        self.assertOrderNote(ENG, [(ENG, FLT, LON), SUP, (ENG, FLT, EDI)], FAR)
    def test_far_support_move(self):
        ''' FAR for supporting movement to a non-adjacent province'''
        self.assertOrderNote(GER, [(GER, AMY, BER), SUP, (GER, AMY, MUN), MTO, RUH], FAR)
    def test_far_support_impossible_move(self):
        ''' FAR for supporting movement to a province the mover can't reach'''
        self.assertOrderNote(GER, [(GER, AMY, BER), SUP, (GER, AMY, MUN), MTO, PRU], FAR)
    def test_far_support_wrong_coast(self):
        ''' FAR for supporting fleet movement to a non-adjacent coastline'''
        self.init_state(SPR, 1901, [
            [TUR, FLT, BLA],
            [TUR, AMY, CON],
        ])
        self.assertOrderNote(TUR, [(TUR, AMY, CON), SUP, (TUR, FLT, BLA), MTO, (BUL, SCS)], FAR)
    def test_far_support_impossible_convoy(self):
        ''' FAR for supporting convoy movement with no possible convoy route'''
        self.assertOrderNote(GER, [(GER, FLT, KIE), SUP, (GER, AMY, BER), MTO, HOL], FAR)
    def test_far_support_fleetless_convoy(self):
        ''' FAR for supporting convoy movement with no fleet to convoy'''
        self.assertOrderNote(GER, [(GER, FLT, KIE), SUP, (GER, AMY, BER), MTO, DEN], FAR)
    def test_far_support_convoy_needing_self(self):
        ''' FAR for supporting convoy movement with convoying fleet'''
        self.init_state(SPR, 1901, [
            [TUR, AMY, ANK],
            [TUR, FLT, BLA],
        ])
        self.assertOrderNote(TUR, [(TUR, AMY, ANK), CTO, RUM, VIA, [BLA]], MBV)
        self.assertOrderNote(TUR, [(TUR, FLT, BLA), SUP, (TUR, AMY, ANK), MTO, RUM], FAR)
    def test_nsu_support_missing_unit_move(self):
        # NSU for attempting to support a move from an empty province.
        self.assertOrderNote(GER, [(GER, AMY, KIE), SUP, (GER, AMY, RUH), MTO, HOL], NSU)
    
    # ConvoyingOrder notes
    def test_far_convoy_impossible_convoy(self):
        ''' FAR for convoying an army with no possible convoy route'''
        self.init_state(SPR, 1901, [
            [GER, AMY, BER],
            [GER, FLT, HEL],
        ])
        self.assertOrderNote(GER, [(GER, FLT, HEL), CVY, (GER, AMY, BER), CTO, HOL], FAR)
    def test_far_convoy_from_inland(self):
        r'''FAR for convoying an army from an inland province'''
        self.init_state(SPR, 1901, [
            [RUS, FLT, IRI],
            [FRA, AMY, RUH],
        ])
        self.assertOrderNote(RUS, [(RUS, FLT, IRI), CVY, (FRA, AMY, RUH), CTO, DEN], FAR)
    def test_far_convoy_to_inland(self):
        r'''FAR for convoying an army to an inland province'''
        self.init_state(SPR, 1901, [
            [RUS, FLT, IRI],
            [FRA, AMY, BEL],
        ])
        self.assertOrderNote(RUS, [(RUS, FLT, IRI), CVY, (FRA, AMY, BEL), CTO, MUN], FAR)
    def test_far_convoy_inland_to_inland(self):
        r'''FAR for convoying an army from inland to inland'''
        self.init_state(SPR, 1901, [
            [RUS, FLT, IRI],
            [FRA, AMY, RUH],
        ])
        self.assertOrderNote(RUS, [(RUS, FLT, IRI), CVY, (FRA, AMY, RUH), CTO, MUN], FAR)
    def test_far_convoy_fleetless_convoy(self):
        ''' FAR for convoying an army with a missing convoy fleet'''
        self.init_state(SPR, 1901, [
            [ENG, AMY, NWY],
            [ENG, FLT, NTH],
        ])
        self.assertOrderNote(ENG, [(ENG, FLT, NTH), CVY, (ENG, AMY, NWY), CTO, KIE], FAR)
    def test_far_convoy_doubled_convoy(self):
        ''' FAR for convoying an army twice through a sea'''
        self.init_state(SPR, 1901, [
            [ENG, AMY, DEN],
            [ENG, FLT, NTH],
            [ENG, FLT, NWG],
            [ENG, FLT, NAO],
            [ENG, FLT, IRI],
            [ENG, FLT, ECH],
        ])
        self.assertOrderNote(ENG, [(ENG, FLT, NWG), CVY, (ENG, AMY, DEN), CTO, HOL], FAR)
    def test_cst_convoying_coast(self):
        ''' CST for attempting to convoy an army to a specific coast.'''
        self.judge.datc.datc_4b6 = 'a'
        self.init_state(FAL, 1901, [
            [RUS, AMY, SWE],
            [RUS, FLT, GOB],
        ])
        self.assertOrderNote(RUS,
            [(RUS, FLT, GOB), CVY, (RUS, AMY, SWE), CTO, (STP, SCS)], CST)
    
    def test_nsp_move(self):
        ''' NSP for movement to a province not on the map'''
        self.assertOrderNote(FRA, [(FRA, AMY, MAR), MTO, SWI], NSP)
    def test_nsp_support(self):
        ''' NSP for supporting movement to a province not on the map'''
        self.assertOrderNote(FRA, [(FRA, AMY, MAR), SUP, (GER, AMY, MUN), MTO, SWI], NSP)
    def test_nsp_retreat(self):
        ''' NSP for retreating to a province not on the map'''
        self.init_state(SPR, 1901, [
            [ITA, AMY, MAR],
            [FRA, AMY, GAS],
            [FRA, AMY, BUR],
        ])
        self.legalOrder(ITA, [(ITA, AMY, MAR), HLD])
        self.legalOrder(FRA, [(FRA, AMY, BUR), MTO, MAR])
        self.legalOrder(FRA, [(FRA, AMY, GAS), SUP, (FRA, AMY, BUR), MTO, MAR])
        self.assertMapState([
            [ITA, AMY, MAR, MRT],
            [FRA, AMY, GAS],
            [FRA, AMY, MAR],
        ])
        self.assertOrderNote(ITA, [(ITA, AMY, MAR), RTO, SWI], NSP)
    
    def test_cst_bicoastal_move(self):
        ''' CST for moving to unspecified coastline when multiple possible'''
        self.init_state(SPR, 1901, [[FRA, FLT, POR]])
        self.assertOrderNote(FRA, [(FRA, FLT, POR), MTO, SPA], CST)
    def test_cst_bicoastal_build(self):
        ''' CST for building on unspecified coastline when multiple possible'''
        self.init_state(WIN, 1901, [])
        self.assertOrderNote(RUS, [(RUS, FLT, STP), BLD], CST)
    def test_cst_inland_build(self):
        ''' CST for building a fleet inland'''
        self.init_state(WIN, 1901, [])
        self.assertOrderNote(RUS, [(RUS, FLT, MOS), BLD], CST)
    def ntest_cst_sea_build(self):
        ''' CST for building an army at sea'''
        # The standard map has no sea supply centers
        raise NotImplementedError
    
    # BuildOrder notes
    def test_ysc(self):
        ''' YSC for building on another power's supply center'''
        self.init_state(WIN, 1901, [])
        self.assertOrderNote(RUS, [(RUS, AMY, BER), BLD], YSC)
    def test_esc(self):
        ''' ESC for building on an occupied supply center'''
        self.init_state(WIN, 1901, [[RUS, AMY, MOS]])
        self.assertOrderNote(RUS, [(RUS, AMY, MOS), BLD], ESC)
    def test_hsc(self):
        ''' HSC for building on a controlled non-home SC'''
        self.chown_sc(RUS, [RUM])
        self.init_state(WIN, 1901, [])
        self.assertOrderNote(RUS, [(RUS, AMY, RUM), BLD], HSC)
    def test_nsc(self):
        ''' NSC for building on a non-SC province'''
        self.init_state(WIN, 1901, [])
        self.assertOrderNote(RUS, [(RUS, AMY, UKR), BLD], NSC)
    
    def ntest_nsu(self): pass
    def ntest_nas(self): pass
    def ntest_nsf(self): pass
    def ntest_nsa(self): pass
    def ntest_nyu(self): pass
    def ntest_nrn(self): pass
    def ntest_nvr(self): pass
    def ntest_nmb(self): pass
    def ntest_nmr(self): pass
    def ntest_nrs(self): pass

if __name__ == '__main__': unittest.main()
