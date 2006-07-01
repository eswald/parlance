''' DATC compliance testing for David's server
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
'''#'''

import unittest
from os         import path
from subprocess import Popen
from sys        import argv, modules
from time       import sleep

import functions
import unittest_datc
import unittest_options
from config     import Configuration, variants
from gameboard  import Map
from main       import ThreadManager
from network    import Client
from player     import Player
from tokens     import DRW, HUH, NOW, THX

# Import all of the DATC test cases
module = modules[__name__]
for name in dir(unittest_datc):
    if name.startswith('DATC'):
        setattr(module, name, getattr(unittest_datc, name))
for name in dir(unittest_options):
    if name.startswith('DATC'):
        setattr(module, name, getattr(unittest_options, name))

# Disable normal failure notices.
def fails(function): return function
functions.fails = fails

# Rearrange the testing system to use a foreign server
class FakePlayer(Player):
    def __init__(self, *args, **kwargs):
        class FakeOrders(object):
            def add(self, order, nation=None): pass
        self.responses = []
        self.__super.__init__(*args, **kwargs)
        self.orders = FakeOrders()
        self.has_NOW = False
    def handle_message(self, message):
        self.responses.append(message)
        self.__super.handle_message(message)
    def handle_NOW(self, message):
        self.has_NOW = True
    def get_reply(self):
        while not self.responses: sleep(.1)
        return self.responses[0]
    def close(self):
        self.send(DRW)
        self.__super.close()
class FakeJudge(object):
    class FakeOptions(object):
        datc_4a3 = 'f'
        def __setattr__(self, name, value):
            print "\n%s=%s\t" % (name, value),
    datc = FakeOptions()
    game_opts = FakeOptions()
    
    def __init__(self, suite): self.suite = suite
    def run(self): return self.suite.wait_now()

def check_results(unit_list, results):
    map_units = [unit[:4] for msg in results
            for unit in msg.fold()[2:] if msg[0] is NOW]
    for unit in unit_list:
        if unit not in map_units: return False
    for unit in map_units:
        if unit not in unit_list: return False
    return True

server_directory = r'D:\Daide\aiserver'
def write_file(self, extension, contents):
    fname = 'test_%s%s%s' % (self.map.name, path.extsep, extension)
    #print 'Writing to', fname
    varfile = open(path.join(server_directory, 'VARIANTS', fname), 'w')
    varfile.write(str(contents) + '\n')
    varfile.close()

def setUp(self):
    ''' Initializes class variables for test cases.'''
    self.set_verbosity(0)
    Configuration._cache.update(self.game_options)
    variant = variants[self.variant_name]
    self.manager = ThreadManager()
    self.players = []
    self.judge = FakeJudge(self)
    self.map = Map(variant)
    self.write_file('mdf', str(variant.map_mdf).replace(' ( ', '\n( '))
    self.write_file('sco', variant.start_sco)
    self.write_file('rem', variant.rep)
def tearDown(self): self.manager.close()
def init_state(self, season, year, unit_list):
    self.write_file('now', NOW(season, year) % unit_list)
    program = [path.join(server_directory, 'AiServer.exe'),
            '-start',
            '-var=test_' + self.map.name,
            '-exit=1',
            '-mtl=3',
            '-rtl=3',
            '-btl=3',
            ]
    process = Popen(program, cwd=server_directory)
    #print "Started '%s' with pid %s" % (str.join(' ', program), process.pid)
    sleep(2)
    for country in self.map.powers:
        client = self.manager.add_client(FakePlayer)
        if not client: raise UserWarning('Thread failed to start!')
        self.players.append(client.player)
    results = self.wait_now()
    if not check_results(unit_list, results):
        raise UserWarning('Incorrectly configured server!')
def wait_now(self):
    player = self.players[-1]
    player.responses = []
    player.has_NOW = False
    tries = 0
    while tries < 30 and not player.has_NOW:
        tries += 1
        self.manager.process()
    return player.responses
def chown_sc(self, owner, sc_list):
    newsco = self.map.create_SCO()
    idx = newsco.index(owner)
    for center in sc_list:
        newsco.remove(center)
        newsco.insert(idx + 1, center)
    self.map.handle_SCO(newsco)
    self.write_file('sco', newsco)
def submitOrder(self, country, order):
    client = [p for t,p in self.players if p.power == country][0]
    client.responses = []
    client.submit(order)
    client.get_reply()
    for msg in client.responses:
        reply = msg[0]
        if reply == THX: reply = msg[-2]; break
        elif reply == HUH: break
    return reply

unittest_datc.DiplomacyAdjudicatorTestCase.write_file = write_file
unittest_datc.DiplomacyAdjudicatorTestCase.setUp = setUp
unittest_datc.DiplomacyAdjudicatorTestCase.tearDown = tearDown
unittest_datc.DiplomacyAdjudicatorTestCase.init_state = init_state
unittest_datc.DiplomacyAdjudicatorTestCase.wait_now = wait_now
unittest_datc.DiplomacyAdjudicatorTestCase.chown_sc = chown_sc
unittest_datc.DiplomacyAdjudicatorTestCase.submitOrder = submitOrder

if __name__ == '__main__':
    if len(argv) > 1 and path.isdir(argv[1]):
        server_directory = argv.pop(1)
    unittest.main()
