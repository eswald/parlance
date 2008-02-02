''' Non-DATC unit tests for the PyDip judge module
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
    
    These are usually simpler than DATC,
    and may test implementation-specific stuff.
'''#'''

import unittest
from time          import time

from config        import variants, Configuration, GameOptions
from functions     import todo
from language      import Token
from main          import Thread
from unittest_datc import DiplomacyAdjudicatorTestCase
from tokens        import *
from xtended       import *

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
        #self.judge.verbosity = 20
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

class Judge_Convoys(DiplomacyAdjudicatorTestCase):
    ''' Minute details of convoy adjudication'''
    
    @todo
    def test_pathless_convoy(self):
        ''' Convoy orders can be sent without a path'''
    @todo
    def test_successful_convoy_path(self):
        ''' Successful pathless convoys have a good path in the ORD message'''
    @todo
    def test_disrupted_convoy_path(self):
        ''' Disrupted pathless convoys have a valid path in the ORD message'''
    @todo
    def test_ignored_convoy_path(self):
        ''' A convoy with a specified path ignores other possible paths'''
        # Lon - Nth - Bel ignores Ech c Lon - Bel
    @todo
    def test_convoy_path_repeated(self):
        ''' A convoy with a specified path uses that path in the ORD message'''

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
    
    def test_disordered_draws(self):
        ''' Draws with different order still the same'''
        #self.judge.verbosity = 20
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

class Judge_Doctests(unittest.TestCase):
    ''' Tests that were once in doctest format.'''
    def setUp(self):
        Configuration.set_globally('verbosity', 0)
    
    def test_startup(self):
        variant = variants['standard']
        judge = variant.new_judge(GameOptions())
        messages = judge.start()
        self.failUnlessEqual([msg[0] for msg in messages], [SCO, NOW])
        self.failUnlessEqual(judge.phase, 0x20)
    def test_attack_calculation(self):
        from orders import MoveOrder
        from judge import Move_Decision, Path_Decision, Attack_Decision
        
        Rome = standard_map.coasts[(AMY, ROM, None)]
        Venice = standard_map.coasts[(AMY, VEN, None)]
        Trieste = standard_map.coasts[(AMY, TRI, None)]
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
        from orders import MoveOrder
        from judge import Move_Decision, Attack_Decision, Prevent_Decision, Hold_Decision
        
        Vienna = standard_map.coasts[(AMY, VIE, None)]
        Galicia = standard_map.coasts[(AMY, GAL, None)]
        Warsaw = standard_map.coasts[(AMY, WAR, None)]
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
    def test_void_convoying_order_result(self):
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

class Judge_Americas(DiplomacyAdjudicatorTestCase):
    ''' Fixing bugs in the Americas4 map variant.'''
    variant_name = 'americas4'
    def test_convoy_problem(self):
        ''' This situation started chewing up memory and CPU like mad.'''
        rep = self.judge.map.opts.rep
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
        if Thread:
            thread = Thread(target=self.judge.handle_SUB, args=(client, sub))
            thread.setDaemon(True)
            thread.start()
            thread.join(10)
            if thread.isAlive(): self.fail('Convoy took too long.')
        else:
            begin = time()
            self.judge.handle_SUB(client, sub)
            end = time()
            self.failUnless(end - begin < 10)

class Judge_Errors(DiplomacyAdjudicatorTestCase):
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
        ''' FAR for an army convoyed with a missing convoy fleet'''
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
    
    # ConvoyingOrder notes
    def test_far_convoy_impossible_convoy(self):
        ''' FAR for convoying an army with no possible convoy route'''
        self.init_state(SPR, 1901, [
            [GER, AMY, BER],
            [GER, FLT, HEL],
        ])
        self.assertOrderNote(GER, [(GER, FLT, HEL), CVY, (GER, AMY, BER), CTO, HOL], FAR)
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
