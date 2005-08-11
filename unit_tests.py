''' Unit Tests not covered by the DATC.
'''#'''

import unittest, datc
from time     import sleep
from sets     import Set
from language import *
from xtended  import *
SWI = Token('SWI', 0x504B)

class Judge_Movement(datc.DiplomacyAdjudicatorTestCase):
    ''' Judge movement phase adjudication'''
    def ptest_army_move_inland(self):
        "Army movement to adjacent inland sector"
        #self.judge.verbosity = 20
        self.init_state(SPR, 1901, [
            [RUS, AMY, MOS],
        ])
        self.legalOrder(RUS, [(RUS, AMY, MOS), MTO, WAR])
        self.assertMapState([
            [RUS, AMY, WAR],
        ])
    def ptest_army_move_coastal(self):
        "Army movement to adjacent coastal sector"
        self.init_state(SPR, 1901, [
            [RUS, AMY, SEV],
        ])
        self.legalOrder(RUS, [(RUS, AMY, SEV), MTO, RUM])
        self.assertMapState([
            [RUS, AMY, RUM],
        ])
    def ptest_army_move_overland(self):
        "Army movement to adjacent overland sector"
        self.init_state(SPR, 1901, [
            [ITA, AMY, VEN],
        ])
        self.legalOrder(ITA, [(ITA, AMY, VEN), MTO, ROM])
        self.assertMapState([
            [ITA, AMY, ROM],
        ])
    def ptest_fleet_move_coastal(self):
        "Fleet movement to adjacent coastal sector"
        self.init_state(SPR, 1901, [
            [RUS, FLT, SEV],
        ])
        self.legalOrder(RUS, [(RUS, FLT, SEV), MTO, RUM])
        self.assertMapState([
            [RUS, FLT, RUM],
        ])
    def ptest_fleet_move_sea(self):
        "Fleet movement to adjacent sea sector"
        self.init_state(SPR, 1901, [
            [RUS, FLT, BAR],
        ])
        self.legalOrder(RUS, [(RUS, FLT, BAR), MTO, NWG])
        self.assertMapState([
            [RUS, FLT, NWG],
        ])
    def ptest_move_support(self):
        "Movement with support to dislodge"
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
    def ptest_hold_support(self):
        "Holding with support against supported attack"
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
    def ptest_convoy(self):
        "Basic convoy"
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
    def ptest_support_coastless(self):
        "Support to move to an unspecified, ambiguous coast"
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

class Judge_Basics(datc.DiplomacyAdjudicatorTestCase):
    "Basic Judge Functionality"
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
        self.failUnlessEqual(Set(retreats), Set(valid))
    def assertDrawn(self, *countries):
        winners = Set(countries)
        messages = self.judge.run()
        for msg in messages:
            if msg[0] is DRW:
                self.failUnlessEqual(winners, Set(msg[2:-1]))
                break
        else: raise self.failureException, 'No draw message in %s' % (messages,)
    def ptest_disordered_draws(self):
        "Draws with different order still the same"
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
        self.acceptable(RUS, DRW([RUS, ENG, FRA]))
        self.acceptable(ENG, DRW([ENG, RUS, FRA]))
        self.acceptable(FRA, DRW([RUS, FRA, ENG]))
        self.acceptable(GER, DRW([FRA, RUS, ENG]))
        self.acceptable(ITA, DRW([FRA, ENG, RUS]))
        self.acceptable(TUR, DRW([ENG, FRA, RUS]))
        self.acceptable(AUS, DRW([FRA, RUS, ENG]))
        self.assertDrawn(FRA, ENG, RUS)
    def ptest_retreat_coasts(self):
        "Fleets retreat to specific coasts"
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
    def ptest_retreat_contested(self):
        "Units cannot retreat to contested areas"
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
    def ptest_multiple_builds(self):
        "Only one unit can be built in a supply center"
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
    def ptest_waives(self):
        "Builds can be waived without error"
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

class Judge_Bugfix(datc.DiplomacyAdjudicatorTestCase):
    "Test cases to reproduce bugs that have been fixed."
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

class Judge_Errors(datc.DiplomacyAdjudicatorTestCase):
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
    # Todo: Write more tests here
    def assertOrderNote(self, country, order, note):
        result = self.submitOrder(country, order)
        self.failUnlessEqual(result, note)
    
    # HoldOrder notes
    # RetreatOrder notes
    # DisbandOrder notes
    # RemoveOrder notes
    # WaiveOrder notes
    
    # MoveOrder notes
    def ptest_far_impossible_move(self):
        ''' FAR for movement to non-adjacent province'''
        self.assertOrderNote(ENG, [(ENG, FLT, LON), MTO, NWY], FAR)
    def ptest_far_inland(self):
        ''' FAR for fleet movement to inland province'''
        self.assertOrderNote(RUS, [(RUS, FLT, SEV), MTO, UKR], FAR)
    def ptest_far_sea(self):
        ''' FAR for army movement to sea province'''
        self.assertOrderNote(FRA, [(FRA, AMY, MAR), MTO, GOL], FAR)
    def ptest_far_wrong_coast(self):
        ''' FAR for fleet movement to a non-adjacent coastline'''
        self.init_state(SPR, 1901, [ (TUR, FLT, BLA) ])
        self.assertOrderNote(TUR, [(TUR, FLT, BLA), MTO, (BUL, SCS)], FAR)
    
    # ConvoyedOrder notes
    def ptest_far_impossible_convoy(self):
        ''' FAR for an army convoyed with no possible convoy route'''
        self.assertOrderNote(GER, [(GER, AMY, BER), CTO, HOL], FAR)
    def ptest_far_fleetless_convoy(self):
        ''' FAR for an army convoyed with a missing convoy fleet'''
        self.init_state(SPR, 1901, [
            [ENG, AMY, NWY],
            [ENG, FLT, NTH],
        ])
        self.assertOrderNote(ENG, [(ENG, AMY, NWY), CTO, KIE, VIA, [NTH, HEL]], FAR)
    def ptest_far_doubled_convoy(self):
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
    def ptest_far_support_hold(self):
        ''' FAR for supporting a hold in a non-adjacent province'''
        self.assertOrderNote(ENG, [(ENG, FLT, LON), SUP, (ENG, FLT, EDI)], FAR)
    def ptest_far_support_move(self):
        ''' FAR for supporting movement to a non-adjacent province'''
        self.assertOrderNote(GER, [(GER, AMY, BER), SUP, (GER, AMY, MUN), MTO, RUH], FAR)
    def ptest_far_support_impossible_move(self):
        ''' FAR for supporting movement to a province the mover can't reach'''
        self.assertOrderNote(GER, [(GER, AMY, BER), SUP, (GER, AMY, MUN), MTO, PRU], FAR)
    def ptest_far_support_wrong_coast(self):
        ''' FAR for supporting fleet movement to a non-adjacent coastline'''
        self.init_state(SPR, 1901, [
            [TUR, FLT, BLA],
            [TUR, AMY, CON],
        ])
        self.assertOrderNote(TUR, [(TUR, AMY, CON), SUP, (TUR, FLT, BLA), MTO, (BUL, SCS)], FAR)
    def ptest_far_support_impossible_convoy(self):
        ''' FAR for supporting convoy movement with no possible convoy route'''
        self.assertOrderNote(GER, [(GER, FLT, KIE), SUP, (GER, AMY, BER), MTO, HOL], FAR)
    def ptest_far_support_fleetless_convoy(self):
        ''' FAR for supporting convoy movement with no fleet to convoy'''
        self.assertOrderNote(GER, [(GER, FLT, KIE), SUP, (GER, AMY, BER), MTO, DEN], FAR)
    def ptest_far_support_convoy_needing_self(self):
        ''' FAR for supporting convoy movement with convoying fleet'''
        self.init_state(SPR, 1901, [
            [TUR, AMY, ANK],
            [TUR, FLT, BLA],
        ])
        self.assertOrderNote(TUR, [(TUR, AMY, ANK), CTO, RUM, VIA, [BLA]], MBV)
        self.assertOrderNote(TUR, [(TUR, FLT, BLA), SUP, (TUR, AMY, ANK), MTO, RUM], FAR)
    
    # ConvoyingOrder notes
    def ptest_far_convoy_impossible_convoy(self):
        ''' FAR for convoying an army with no possible convoy route'''
        self.init_state(SPR, 1901, [
            [GER, AMY, BER],
            [GER, FLT, HEL],
        ])
        self.assertOrderNote(GER, [(GER, FLT, HEL), CVY, (GER, AMY, BER), CTO, HOL], FAR)
    def ptest_far_convoy_fleetless_convoy(self):
        ''' FAR for convoying an army with a missing convoy fleet'''
        self.init_state(SPR, 1901, [
            [ENG, AMY, NWY],
            [ENG, FLT, NTH],
        ])
        self.assertOrderNote(ENG, [(ENG, FLT, NTH), CVY, (ENG, AMY, NWY), CTO, KIE], FAR)
    def ptest_far_convoy_doubled_convoy(self):
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
    
    def ptest_nsp_move(self):
        ''' NSP for movement to a province not on the map'''
        self.assertOrderNote(FRA, [(FRA, AMY, MAR), MTO, SWI], NSP)
    def ptest_nsp_support(self):
        ''' NSP for supporting movement to a province not on the map'''
        self.assertOrderNote(FRA, [(FRA, AMY, MAR), SUP, (GER, AMY, MUN), MTO, SWI], NSP)
    def ptest_nsp_retreat(self):
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
    
    def ptest_cst_bicoastal_move(self):
        ''' CST for moving to unspecified coastline when multiple possible'''
        self.init_state(SPR, 1901, [[FRA, FLT, POR]])
        self.assertOrderNote(FRA, [(FRA, FLT, POR), MTO, SPA], CST)
    def ptest_cst_bicoastal_build(self):
        ''' CST for building on unspecified coastline when multiple possible'''
        self.init_state(WIN, 1901, [])
        self.assertOrderNote(RUS, [(RUS, FLT, STP), BLD], CST)
    def ptest_cst_inland_build(self):
        ''' CST for building a fleet inland'''
        self.init_state(WIN, 1901, [])
        self.assertOrderNote(RUS, [(RUS, FLT, MOS), BLD], CST)
    def ntest_cst_sea_build(self):
        ''' CST for building an army at sea'''
        # The standard map has no sea supply centers
        raise NotImplementedError
    
    # BuildOrder notes
    def ptest_ysc(self):
        ''' YSC for building on another power's supply center'''
        self.init_state(WIN, 1901, [])
        self.assertOrderNote(RUS, [(RUS, AMY, BER), BLD], YSC)
    def ptest_esc(self):
        ''' ESC for building on an occupied supply center'''
        self.init_state(WIN, 1901, [[RUS, AMY, MOS]])
        self.assertOrderNote(RUS, [(RUS, AMY, MOS), BLD], ESC)
    def ptest_hsc(self):
        ''' HSC for building on a controlled non-home SC'''
        self.chown_sc(RUS, [RUM])
        self.init_state(WIN, 1901, [])
        self.assertOrderNote(RUS, [(RUS, AMY, RUM), BLD], HSC)
    def ptest_nsc(self):
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

class Server_Basics(unittest.TestCase):
    "Basic Server Functionality"
    from network import Verbose_Object, Connection
    class Fake_Player(Verbose_Object):
        ''' A false player, to test the network classes.
            Also useful to learn country passcodes.
        '''#'''
        def __init__(self, send_method, representation):
            from language import NME
            self.log_debug(9, 'Fake player started')
            self.closed = False
            self.send = send_method
            self.rep = representation
            send_method(NME('Loose connection', 'Fake_Player'))
        def close(self):
            self.log_debug(9, 'Closed')
            self.closed = True
        def handle_message(self, message):
            from language import HLO, MAP, SVE, LOD
            self.log_debug(5, '<< %s', message)
            if message[0] is HLO:
                sleep(14)
                self.send(ADM(str(message[2]), 'Passcode: %d' % message[5].value()))
                self.close()
            elif message[0] in (MAP, SVE, LOD): self.send(YES(message))
    class Fake_Client(Connection):
        ''' A fake Client to test the server timeout.'''
        is_server = False
        def prefix(self): return 'Fake Client'
        prefix = property(fget=prefix)
        
        def __init__(self, send_IM):
            'Initializes instance variables'
            self.__super.__init__()
            self.initialize = send_IM
        def open(self):
            import socket
            # Open the socket
            self.sock = sock = socket.socket()
            sock.connect((self.opts.host, self.opts.port))
            sock.settimeout(None)
            
            # Required by the DCSP document
            try: sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            except: self.log_debug(7, 'Could not set SO_KEEPALIVE')
            
            if self.initialize:
                # Send initial message
                self.log_debug(9, 'Sending Initial Message')
                self.send_dcsp(self.IM, pack('!HH', self.opts.dcsp_version, self.opts.magic));
                
                # Wait for representation message
                while not (self.closed or self.rep):
                    result = self.read()
                    if result: self.log_debug(7, str(result) + ' while waiting for RM')
                if self.rep: self.log_debug(9, 'Representation received')
                
                # Set a reasonable timeout.
                # Without this, we don't check for client death until
                # the next server message; in some cases, until it dies.
                #sock.settimeout(30)
                
                # Create the Player
                if self.rep and not self.closed:
                    self.player = self.pclass(self.send, self.rep, **self.kwargs)
                    return True
            return False
        def read_error(self, code):
            self.log_debug(1, 'Expecting error #%d (%s)',
                    code, config.error_strings.get(code))
            self.error_code = None
            self.read()
            assert self.error_code == code
        def send_error(self, code, from_them=False):
            if from_them: self.error_code = code
            self.__super.send_error(code, from_them)
    
    game_options = {
            'syntax Level': 0,
            'variant name' : 'standard',
            'close on disconnect' : True,
            'use internal server' : True,
            'host' : '',
            'port' : 16719,
            'timeout for select() without deadline' : 5,
            'publish order sets': False,
            'publish individual orders': False,
            'static years before setting draw': 3,
    }
    def setUp(self):
        ''' Initializes class variables for test cases.'''
        self.set_verbosity(7)
        config.option_class.local_opts.update(self.game_options)
        self.server = None
        self.threads = []
    def tearDown(self):
        if self.server and not self.server.closed: self.server.close()
        for thread in self.threads:
            if thread.isAlive(): thread.join()
    def set_verbosity(self, verbosity):
        from functions import Verbose_Object
        Verbose_Object.verbosity = verbosity
    def connect_server(self, clients, games=1, poll=True):
        from network import ServerSocket, Client
        config.option_class.local_opts.update({'number of games' : games})
        self.server = server = ServerSocket()
        if not poll: server.polling = None
        s_thread = server.start()
        assert s_thread
        self.threads.append(s_thread)
        try:
            for dummy in range(games):
                assert not server.closed
                threads = []
                for player_class in clients:
                    thread = Client(player_class).start()
                    assert thread
                    threads.append(thread)
                for thread in threads:
                    if thread.isAlive(): thread.join()
        except:
            self.threads.extend(threads)
            server.close()
            raise
    def ptest_timeout(self):
        "Thirty-second timeout for the Initial Message"
        self.set_verbosity(15)
        self.connect_server([])
        client = self.Fake_Client(False)
        client.open()
        sleep(45)
        client.read_error(client.opts.Timeout)
    def ptest_full_connection(self):
        "Seven fake players, polling if possible"
        self.set_verbosity(15)
        self.connect_server([self.Fake_Player] * 7)
    def ptest_without_poll(self):
        "Seven fake players, selecting"
        self.set_verbosity(15)
        self.connect_server([self.Fake_Player] * 7, poll=False)
    def ptest_with_timer(self):
        "Seven fake players and an observer"
        from player  import Clock
        self.connect_server([Clock] + ([self.Fake_Player] * 7))
    def ptest_holdbots(self):
        "Seven drawing holdbots"
        from player import HoldBot
        self.connect_server([HoldBot] * 7)
    def ptest_one_dumbbot(self):
        "Six drawing holdbots and a dumbbot"
        from player  import HoldBot
        from dumbbot import DumbBot
        self.set_verbosity(1)
        DumbBot.verbosity = 20
        self.connect_server([DumbBot, HoldBot, HoldBot,
                HoldBot, HoldBot, HoldBot, HoldBot])
    def ptest_dumbbots(self):
        "seven dumbbots"
        from dumbbot import DumbBot
        self.connect_server([DumbBot] * 7)
    def ptest_two_games(self):
        "seven holdbots; two games"
        self.set_verbosity(4)
        from player import HoldBot
        self.connect_server([HoldBot] * 7, 2)

if __name__ == '__main__': unittest.main()

# vim: sts=4 sw=4 et tw=75 fo=crql1
