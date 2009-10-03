r'''DAIDE compatibility testing for Parlance
    Copyright (C) 2004-2009  Eric Wald
    
    This module runs Parlance test cases on David's server, to check whether
    and under what conditions the two servers act the same.  Many of these
    tests will fail, particularly those that require specific option settings.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

import unittest
from itertools  import count
from os         import path
from subprocess import Popen
from sys        import argv, modules
from time       import sleep

import parlance.test

# Disable normal failure notices.
def fails(function): return function
parlance.test.fails = fails

from parlance.test       import datc, options
from parlance.config     import Configuration, variants
from parlance.gameboard  import Map
from parlance.main       import ThreadManager
from parlance.player     import Player
from parlance.tokens     import DRW, HUH, NOW, THX
from parlance.xtended    import standard_now

# Import all of the DATC test cases
module = modules[__name__]
for name in dir(datc):
    if name.startswith('DATC'):
        setattr(module, name, getattr(datc, name))
for name in dir(options):
    if name.startswith('DATC'):
        setattr(module, name, getattr(options, name))

# Rearrange the testing system to use a foreign server
class FakePlayer(Player):
    def __init__(self, *args, **kwargs):
        class FakeOrders(object):
            def add(self, order, nation=None): pass
        self.responses = []
        self.__super.__init__(*args, **kwargs)
        self.orders = FakeOrders()
        self.has_NOW = False
        self.done = False
    def handle_message(self, message):
        self.responses.append(message)
        self.__super.handle_message(message)
    def handle_NOW(self, message):
        if self.done: self.send(DRW)
        self.has_NOW = True
    def handle_MIS(self, message):
        pass
    def get_reply(self):
        while not self.responses:
            self.manager.process(.1)
        return self.responses[0]
    def finish(self):
        self.send(DRW)
        self.done = True
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

server_directory = r"/home/eswald/Programs/parlance/extern/daide/aiserver"
def write_file(self, extension, contents):
    fname = 'test_%s%s%s' % (self.map.name, path.extsep, extension)
    #print 'Writing to', fname
    varfile = open(path.join(server_directory, 'VARIANTS', fname), 'w')
    varfile.write(str(contents) + '\n')
    varfile.close()

port = count(16714)
def setUp(self):
    ''' Initializes class variables for test cases.'''
    self.set_verbosity(0)
    self.game_options['port'] = port.next()
    Configuration._cache.update(self.game_options)
    variant = variants[self.variant_name]
    self.manager = ThreadManager()
    self.manager.options.block_exceptions = False
    self.players = []
    self.judge = FakeJudge(self)
    self.map = Map(variant)
    self.write_file('mdf', str(variant.mdf()).replace(' ( ', '\n( '))
    self.write_file('sco', variant.sco())
    self.write_file('rem', variant.rep)
def tearDown(self):
    #print "Tearing Down..."
    for player in self.players:
        player.finish()
    self.manager.process(5)
    for player in self.players:
        player.close()
    self.manager.process(5)
    self.manager.close()
    sleep(2)
def init_state(self, season, year, unit_list):
    self.write_file('now', NOW(season, year) % unit_list)
    program = [path.join(server_directory, 'AiServer.exe'),
        '-start',
        '-var=test_' + self.map.name,
        '-exit=1',
        '-mtl=3',
        '-rtl=3',
        '-btl=3',
        '-port=' + str(Configuration._cache['port']),
        '-kill=1',
    ]
    process = Popen(program, cwd=server_directory)
    #print dir(process)
    #print "Started '%s' with pid %s" % (str.join(' ', program), process.pid)
    sleep(2)
    for country in self.map.powers:
        #print "Starting %s..." % country
        tries = 4
        while True:
            try:
                client = self.manager.add_client(FakePlayer)
            except:
                if not tries: raise
                tries -= 1
                sleep(2)
            else:
                break
        if not client: raise UserWarning('Thread failed to start!')
        if not client.player: self.manager.process(0.1)
        self.players.append(client.player)
    results = self.wait_now()
    if not check_results(unit_list, results):
        raise UserWarning('Incorrectly configured server!')
def wait_now(self):
    #print "Waiting for NOW..."
    player = [p for p in self.players if not p.closed][-1]
    tries = 0
    while tries < 30 and not player.has_NOW:
        tries += 1
        self.manager.process()
    results = player.responses
    for player in self.players:
        player.responses = []
        player.has_NOW = False
    return results
def chown_sc(self, owner, sc_list):
    newsco = self.map.create_SCO()
    idx = newsco.index(owner)
    for center in sc_list:
        newsco.remove(center)
        newsco.insert(idx + 1, center)
    self.map.handle_SCO(newsco)
    self.write_file('sco', newsco)
def submitOrder(self, country, order):
    if not self.players:
        now = standard_now.fold()
        self.init_state(now[1][0], now[1][1], now[2:])
    client = [p for p in self.players if p.power == country][0]
    client.responses = []
    client.submit(order)
    client.get_reply()
    for msg in client.responses:
        reply = msg[0]
        if reply == THX: reply = msg[-2]; break
        elif reply == HUH: break
    return reply

datc.DiplomacyAdjudicatorTestCase.write_file = write_file
datc.DiplomacyAdjudicatorTestCase.setUp = setUp
datc.DiplomacyAdjudicatorTestCase.tearDown = tearDown
datc.DiplomacyAdjudicatorTestCase.init_state = init_state
datc.DiplomacyAdjudicatorTestCase.wait_now = wait_now
datc.DiplomacyAdjudicatorTestCase.chown_sc = chown_sc
datc.DiplomacyAdjudicatorTestCase.submitOrder = submitOrder

if __name__ == '__main__':
    if len(argv) > 1 and path.isdir(argv[1]):
        server_directory = argv.pop(1)
    unittest.main()
