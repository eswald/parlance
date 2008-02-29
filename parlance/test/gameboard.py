r'''Test cases for the Parlance gameboard and unit orders
    Copyright (C) 2004-2008  Eric Wald
    
    A few of these tests currently fail, because the features they test are
    only allowed under AOA or certain rule variants.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

import unittest

from parlance.config     import parse_file, read_representation_file
from parlance.config     import MapVariant, variants
from parlance.functions  import fails
from parlance.gameboard  import Map, Province, Turn, Variant
from parlance.judge      import DatcOptions
from parlance.language   import IntegerToken, protocol
from parlance.orders     import createUnitOrder
from parlance.tokens     import *
from parlance.validation import Validator
from parlance.xtended    import *

class VariantTests(unittest.TestCase):
    "Tests for loading information from a variant file"
    def load(self, information):
        variant = Variant("testing")
        variant.parse(line.strip() for line in information.split("\n"))
        return variant
    
    def test_default_name(self):
        variant = Variant("testing")
        self.failUnlessEqual(variant.name, "testing")
    def test_name_loaded(self):
        variant = self.load('''
            [variant]
            name=Something
        ''')
        self.failUnlessEqual(variant.name, "Something")
    def test_default_mapname(self):
        variant = Variant("testing")
        self.failUnlessEqual(variant.mapname, "testing")
    def test_mapname_loaded(self):
        variant = self.load('''
            [variant]
            mapname=Something
        ''')
        self.failUnlessEqual(variant.mapname, "Something")
    def test_default_description(self):
        variant = Variant("testing")
        self.failUnlessEqual(variant.description, "")
    def test_description_loaded(self):
        variant = self.load('''
            [variant]
            description=Something
        ''')
        self.failUnlessEqual(variant.description, "Something")
    def test_default_judge(self):
        variant = Variant("testing")
        self.failUnlessEqual(variant.judge, "standard")
    def test_judge_loaded(self):
        variant = self.load('''
            [variant]
            judge=Something
        ''')
        self.failUnlessEqual(variant.judge, "Something")
    def test_default_start(self):
        variant = Variant("testing")
        self.failUnlessEqual(variant.start, "SPR 0")
    def test_start_loaded(self):
        variant = self.load('''
            [variant]
            start=WIN 2000
        ''')
        self.failUnlessEqual(variant.start, "WIN 2000")
    
    def test_default_powers(self):
        variant = Variant("testing")
        self.failUnlessEqual(variant.powers, {})
    def test_powers_both(self):
        variant = self.load('''
            [powers]
            ONE=name,adj
        ''')
        self.failUnlessEqual(variant.powers, {"ONE": ("name", "adj")})
    def test_powers_name(self):
        variant = self.load('''
            [powers]
            TWO=someone
        ''')
        self.failUnlessEqual(variant.powers, {"TWO": ("someone", "someone")})
    def test_powers_empty(self):
        variant = self.load('''
            [powers]
            TRE=
        ''')
        self.failUnlessEqual(variant.powers, {"TRE": ("TRE", "TRE")})
    def test_powers_multiple(self):
        variant = self.load('''
            [powers]
            ONE=name,adj
            TWO=someone,somewhere
        ''')
        self.failUnlessEqual(variant.powers, {
                "ONE": ("name", "adj"),
                "TWO": ("someone", "somewhere"),
        })
    
    def test_default_provinces(self):
        variant = Variant("testing")
        self.failUnlessEqual(variant.provinces, {})
    def test_provinces_name(self):
        variant = self.load('''
            [provinces]
            TWO=somewhere
        ''')
        self.failUnlessEqual(variant.provinces, {"TWO": "somewhere"})
    def test_provinces_empty(self):
        variant = self.load('''
            [provinces]
            ONE=
        ''')
        self.failUnlessEqual(variant.provinces, {"ONE": "ONE"})
    def test_provinces_multiple(self):
        variant = self.load('''
            [provinces]
            ONE=name
            TWO=somewhere
        ''')
        self.failUnlessEqual(variant.provinces, {
                "ONE": "name",
                "TWO": "somewhere",
        })

class Map_Bugfix(unittest.TestCase):
    ''' Tests to reproduce bugs related to the Map class'''
    def test_empty_UNO(self):
        ''' Test whether Map can define maps with no non-home supply centers.'''
        # Almost Standard...
        mdf = '''
            MDF (AUS ENG FRA GER ITA RUS TUR)
            (((AUS bud tri vie)(ENG edi lon lvp)(FRA bre mar par)
              (GER ber kie mun)(ITA nap rom ven)(RUS mos sev stp war)
              (TUR ank con smy bel bul den gre hol nwy por rum ser spa swe tun)
              (UNO))
             (alb apu arm boh bur cly fin gal gas lvn naf pic pie pru ruh sil syr
              tus tyr ukr wal yor adr aeg bal bar bla gob eas ech hel ion iri gol
              mao nao nth nwg ska tys wes))
            ((adr(FLT alb apu ven tri ion))
             (aeg(FLT gre (bul scs) con smy eas ion))
             (alb(AMY tri gre ser)(FLT adr tri gre ion))
             (ank(AMY arm con smy)(FLT bla arm con))
             (apu(AMY ven nap rom)(FLT ven adr ion nap))
             (arm(AMY smy syr ank sev)(FLT ank sev bla))
             (bal(FLT lvn pru ber kie den swe gob))
             (bar(FLT nwg (stp ncs) nwy))
             (bel(AMY hol pic ruh bur)(FLT ech nth hol pic))
             (ber(AMY kie pru sil mun)(FLT kie bal pru))
             (bla(FLT rum sev arm ank con (bul ecs)))
             (boh(AMY mun sil gal vie tyr))
             (gob(FLT swe fin (stp scs) lvn bal))
             (bre(AMY pic gas par)(FLT mao ech pic gas))
             (bud(AMY vie gal rum ser tri))
             (bul((FLT ECS) con bla rum)(AMY gre con ser rum)((FLT SCS) gre aeg con))
             (bur(AMY mar gas par pic bel ruh mun))
             (cly(AMY edi lvp)(FLT edi lvp nao nwg))
             (con(AMY bul ank smy)(FLT (bul scs) (bul ecs) bla ank smy aeg))
             (den(AMY swe kie)(FLT hel nth swe bal kie ska))
             (eas(FLT syr smy aeg ion))
             (edi(AMY lvp yor cly)(FLT nth nwg cly yor))
             (ech(FLT mao iri wal lon nth bel pic bre))
             (fin(AMY swe stp nwy)(FLT swe (stp scs) gob))
             (gal(AMY war ukr rum bud vie boh sil))
             (gas(AMY par bur mar spa bre)(FLT (spa ncs) mao bre))
             (gre(AMY bul alb ser)(FLT (bul scs) aeg ion alb))
             (hel(FLT nth den kie hol))
             (hol(AMY bel kie ruh)(FLT bel nth hel kie))
             (ion(FLT tun tys nap apu adr alb gre aeg eas))
             (iri(FLT nao lvp wal ech mao))
             (kie(AMY hol den ber mun ruh)(FLT hol hel den bal ber))
             (lon(AMY yor wal)(FLT yor nth ech wal))
             (lvn(AMY pru stp mos war)(FLT pru bal gob (stp scs)))
             (lvp(AMY wal edi yor cly)(FLT wal iri nao cly))
             (gol(FLT (spa scs) mar pie tus tys wes))
             (mao(FLT nao iri ech bre gas (spa ncs) por (spa scs) naf wes))
             (mar(AMY spa pie gas bur)(FLT (spa scs) gol pie))
             (mos(AMY stp lvn war ukr sev))
             (mun(AMY bur ruh kie ber sil boh tyr))
             (naf(AMY tun)(FLT mao wes tun))
             (nao(FLT nwg lvp iri mao cly))
             (nap(AMY rom apu)(FLT rom tys ion apu))
             (nwy(AMY fin stp swe)(FLT ska nth nwg bar (stp ncs) swe))
             (nth(FLT yor edi nwg nwy ska den hel hol bel ech lon))
             (nwg(FLT nao bar nwy nth cly edi))
             (par(AMY bre pic bur gas))
             (pic(AMY bur par bre bel)(FLT bre ech bel))
             (pie(AMY mar tus ven tyr)(FLT mar gol tus))
             (por(AMY spa)(FLT mao (spa ncs) (spa scs)))
             (pru(AMY war sil ber lvn)(FLT ber bal lvn))
             (rom(AMY tus nap ven apu)(FLT tus tys nap))
             (ruh(AMY bur bel hol kie mun))
             (rum(AMY ser bud gal ukr sev bul)(FLT sev bla (bul ecs)))
             (ser(AMY tri bud rum bul gre alb))
             (sev(AMY ukr mos rum arm)(FLT rum bla arm))
             (sil(AMY mun ber pru war gal boh))
             (ska(FLT nth nwy den swe))
             (smy(AMY syr con ank arm)(FLT syr eas aeg con))
             (spa(AMY gas por mar)((FLT NCS) gas mao por)((FLT SCS) por wes gol mar mao))
             (stp(AMY fin lvn nwy mos)((FLT NCS) bar nwy)((FLT SCS) fin lvn gob))
             (swe(AMY fin den nwy)(FLT fin gob bal den ska nwy))
             (syr(AMY smy arm)(FLT eas smy))
             (tri(AMY tyr vie bud ser alb ven)(FLT alb adr ven))
             (tun(AMY naf)(FLT naf wes tys ion))
             (tus(AMY rom pie ven)(FLT rom tys gol pie))
             (tyr(AMY mun boh vie tri ven pie))
             (tys(FLT wes gol tus rom nap ion tun))
             (ukr(AMY rum gal war mos sev))
             (ven(AMY tyr tus rom pie apu tri)(FLT apu adr tri))
             (vie(AMY tyr boh gal bud tri))
             (wal(AMY lvp lon yor)(FLT lvp iri ech lon))
             (war(AMY sil pru lvn mos ukr gal))
             (wes(FLT mao (spa scs) gol tys tun naf))
             (yor(AMY edi lon lvp wal)(FLT edi nth lon))
            )
        '''#'''
        standard = variants['standard']
        options = MapVariant(standard.variant,
            standard.description, standard.files)
        options.map_mdf = options.rep.translate(mdf)
        options.map_name = 'standard_empty_UNO'
        game_map = Map(options)
        if not game_map.valid: self.fail(game_map.define(options.map_mdf))
    def test_island_Pale(self):
        ''' Check for The Pale in Hundred3, which is an island.'''
        options = variants['hundred3']
        game_map = Map(options)
        prov = options.rep['PAL']
        self.failUnless(prov.category_name().split()[0] == 'Coastal')
        coast = game_map.coasts[(AMY, prov, None)]
        self.failUnless(coast.is_valid())
        self.failUnless(coast.province.is_valid())
    def test_island_province(self):
        ''' Test whether Province can define island spaces.'''
        island = Province(NAF, [[AMY], [FLT, MAO, WES]], None)
        self.failUnless(island.is_valid())
    def test_cache_mdf(self):
        opts = MapVariant('testing', 'Test map', {})
        Map(opts).handle_MDF(variants['standard'].map_mdf)
        new_map = Map(opts)
        self.failUnless(new_map.valid)

class Coast_Bugfix(unittest.TestCase):
    ''' Tests to reproduce bugs related to the Coast class'''
    def test_infinite_convoy(self):
        variant = variants['americas4']
        board = Map(variant)
        Alaska = board.spaces[variant.rep['ALA']]
        Oregon = board.coasts[(AMY, variant.rep['ORE'], None)]
        results = Oregon.convoy_routes(Alaska, board)
        self.failUnlessEqual(results, [])

class Order_Strings(unittest.TestCase):
    def check_order(self, order, result):
        order = createUnitOrder(order, standard_map.powers[FRA],
                standard_map, DatcOptions())
        self.failUnlessEqual(str(order), result)
    def test_hold_string(self):
        self.check_order([[FRA, FLT, BRE], HLD], 'Fleet Brest HOLD')
    def test_hold_coastal(self):
        self.check_order([[FRA, FLT, [SPA, SCS]], HLD],
                'Fleet Spain (south coast) HOLD')
    def test_move_string(self):
        self.check_order([[FRA, FLT, BRE], MTO, MAO],
                'Fleet Brest -> Mid-Atlantic Ocean')
    def test_move_to_coast(self):
        self.check_order([[FRA, FLT, MAO], MTO, [SPA, SCS]],
                'Fleet Mid-Atlantic Ocean -> Spain (south coast)')
    def test_move_from_coast(self):
        self.check_order([[FRA, FLT, [SPA, SCS]], MTO, MAO],
                'Fleet Spain (south coast) -> Mid-Atlantic Ocean')
    
    def test_support_hold_string(self):
        self.check_order([[FRA, FLT, BRE], SUP, MAO, HLD],
                'Fleet Brest SUPPORT Fleet Mid-Atlantic Ocean')
    def test_support_hold_ambiguous(self):
        # Perhaps not the best form, but it works.
        self.check_order([[FRA, FLT, BRE], SUP, GAS, HLD],
                'Fleet Brest SUPPORT  Gascony')
    def test_support_hold_foreign(self):
        self.check_order([[FRA, FLT, BRE], SUP, LON, HLD],
                'Fleet Brest SUPPORT English Fleet London')
    def test_support_move_string(self):
        self.check_order([[FRA, AMY, PAR], SUP, MAR, MTO, GAS],
                'Army Paris SUPPORT Army Marseilles -> Gascony')
    
    def test_convoying_string(self):
        self.check_order([[FRA, FLT, BRE], CVY, MAR, CTO, GAS],
                'Fleet Brest CONVOY Army Marseilles -> Gascony')
    def test_convoyed_string(self):
        self.check_order([[FRA, AMY, MAR], CTO, GAS, VIA, [BRE]],
                'Army Marseilles -> Brest -> Gascony')
    def test_convoyed_long(self):
        self.check_order([[FRA, AMY, MAR], CTO, GAS, VIA, [GOL, WES, MAO]],
                'Army Marseilles -> Gulf of Lyon -> Western Mediterranean Sea -> Mid-Atlantic Ocean -> Gascony')
    
    def test_retreat_string(self):
        self.check_order([[FRA, AMY, PAR], RTO, GAS],
                'Army Paris -> Gascony')
    def test_disband_string(self):
        self.check_order([[FRA, AMY, PAR], DSB],
                'Army Paris DISBAND')
    
    def test_build_string(self):
        self.check_order([[FRA, AMY, PAR], BLD],
                'Builds an army in Paris')
    @fails
    def test_build_foreign(self):
        self.check_order([[GER, AMY, PAR], BLD],
                'Builds a German army in Paris')
    def test_remove_string(self):
        self.check_order([[FRA, AMY, PAR], REM],
                'Removes the army in Paris')
    @fails
    def test_remove_foreign(self):
        self.check_order([[GER, AMY, PAR], REM],
                'Removes the German army in Paris')
    def test_waive_string(self):
        self.check_order([FRA, WVE],
                'Waives a build')
    @fails
    def test_waive_foreign(self):
        self.check_order([GER, WVE],
                'Waives a German build')

class Gameboard_Doctests(unittest.TestCase):
    ''' Tests that were once doctests, but no longer work as such.'''
    def test_map_define(self):
        ''' Test the creation of a new map from a simple MDF.'''
        
        mdf = MDF (ENG, FRA) ([
            (ENG, EDI, LON),
            (FRA, BRE, PAR),
            ([ENG, FRA], BEL, HOL),
            (UNO, SPA, NWY),
        ], [ECH, NTH, PIC]) (
            (EDI, [AMY, LON], [FLT, NTH]),
            (LON, [AMY, EDI], [FLT, NTH, ECH]),
            (BRE, [AMY, PAR, PIC, SPA], [FLT, ECH, PIC, (SPA, NCS)]),
            (PAR, [AMY, PAR, SPA, PIC]),
            (BEL, [AMY, PIC, HOL], [FLT, NTH, ECH, PIC, HOL]),
            (HOL, [AMY, BEL], [FLT, NTH]),
            (SPA, [AMY, PAR, BRE], [(FLT, NCS), BRE]),
            (NWY, [AMY], [FLT, NTH]),
            (ECH, [FLT, NTH, BRE, LON, BEL, PIC]),
            (NTH, [FLT, ECH, BEL, HOL, LON, NWY, EDI]),
            (PIC, [AMY, BRE, PAR, BEL], [FLT, ECH, BRE, BEL]),
        )
        
        self.failIf(Validator().validate_server_message(mdf),
                'Invalid MDF message')
        m = Map(MapVariant('simplified',
            'Small board for testing purposes', {},
            protocol.default_rep))
        self.failIf(m.valid, 'Map valid before MDF')
        result = m.define(mdf)
        self.failIf(result, result)
    def test_turn_compare_lt(self):
        spring = Turn(SPR, 1901)
        fall = Turn(FAL, 1901)
        self.failUnlessEqual(cmp(spring, fall), -1)
    def test_turn_compare_gt(self):
        spring = Turn(SPR, 1901)
        fall = Turn(FAL, 1901)
        self.failUnlessEqual(cmp(fall, spring.key), 1)
    def test_turn_compare_eq(self):
        fall = Turn(FAL, 1901)
        self.failUnlessEqual(cmp(fall, fall.key), 0)
    def test_turn_phase_hex(self):
        t = Turn(SUM, 1901)
        self.failUnlessEqual(t.phase(), 0x40)
    def test_turn_phase_name(self):
        t = Turn(SUM, 1901)
        self.failUnlessEqual(t.phase(), Turn.retreat_phase)
    
    # Tests from other modules
    def test_read_representation_file(self):
        ''' Tests the config.read_representation_file() function.'''
        rep = parse_file('variants/sailho.rem', read_representation_file)
        self.failUnlessEqual(repr(rep['NTH']), "Token('NTH', 0x4100)")
        
        # This used to be 'Psy'; it was probably changed for consistency.
        self.failUnlessEqual(repr(rep[0x563B]), "Token('PSY', 0x563B)")
        self.failUnlessEqual(len(rep), 64)

if __name__ == '__main__': unittest.main()
