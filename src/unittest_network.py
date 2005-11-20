''' Unit tests for the Network module.
'''#'''

import unittest
from time      import sleep
from functions import Verbose_Object
from unittest_server import ServerTestCase

class Network_Basics(ServerTestCase):
    class Disconnector(ServerTestCase.Fake_Player):
        sleep_time = 14
        name = 'Loose connection'
        def handle_message(self, message):
            from language import HLO, ADM
            self.__super.handle_message(message)
            if message[0] is HLO:
                sleep(self.sleep_time)
                self.send(ADM(str(self.power), 'Passcode: %d' % self.pcode))
                self.close()
    
    def test_timeout(self):
        "Thirty-second timeout for the Initial Message"
        self.set_verbosity(15)
        self.connect_server_threaded([])
        client = self.Fake_Client(False)
        client.open()
        sleep(45)
        client.read_error(client.opts.Timeout)
    def test_full_connection(self):
        "Seven fake players, polling if possible"
        self.set_verbosity(15)
        self.connect_server_threaded([self.Disconnector] * 7)
    def test_without_poll(self):
        "Seven fake players, selecting"
        self.set_verbosity(15)
        self.connect_server_threaded([self.Disconnector] * 7, poll=False)
    def test_with_timer(self):
        "Seven fake players and an observer"
        from player  import Clock
        self.connect_server([Clock] + ([self.Disconnector] * 7))
    def test_takeover(self):
        "Takeover ability after game start"
        class Fake_Takeover(Verbose_Object):
            ''' A false player, who takes over a position and then quits.'''
            sleep_time = 7
            def __init__(self, send_method, representation, power, passcode):
                from language import IAM
                self.log_debug(9, 'Fake player started')
                self.restarted = False
                self.closed = False
                self.send = send_method
                self.rep = representation
                self.power = power
                send_method(IAM(power, passcode))
            def close(self):
                self.log_debug(9, 'Closed')
                self.closed = True
            def handle_message(self, message):
                from language import YES, IAM, ADM
                self.log_debug(5, '<< %s', message)
                if message[0] is YES and message[2] is IAM:
                    self.send(ADM(self.power.text, 'Takeover successful'))
                    sleep(self.sleep_time)
                    self.close()
                else: raise AssertionError, 'Unexpected message: ' + str(message)
        class Fake_Restarter(self.Disconnector):
            ''' A false player, who starts Fake_Takeover after receiving HLO.'''
            sleep_time = 3
            def close(self):
                from network import Client
                thread = Client(Fake_Takeover, power=self.power,
                    passcode=self.pcode).start()
                assert thread
                thread.join()
                self.log_debug(9, 'Closed')
                self.closed = True
        self.set_verbosity(15)
        self.connect_server_threaded([Fake_Restarter] + [self.Disconnector] * 6)

class Network_Full_Games(ServerTestCase):
    def connect_server(self, *args):
        ServerTestCase.connect_server(self, *args)
        while not self.server.closed: sleep(3); self.server.check()
    def test_holdbots(self):
        "Seven drawing holdbots"
        from player import HoldBot
        self.connect_server([HoldBot] * 7)
    def test_one_dumbbot(self):
        "Six drawing holdbots and a dumbbot"
        from player  import HoldBot
        from dumbbot import DumbBot
        self.set_verbosity(1)
        DumbBot.verbosity = 20
        self.connect_server([DumbBot, HoldBot, HoldBot,
                HoldBot, HoldBot, HoldBot, HoldBot])
    def test_dumbbots(self):
        "seven dumbbots, quick game"
        from dumbbot import DumbBot
        self.connect_server([DumbBot] * 7)
    def test_two_games(self):
        "seven holdbots; two games"
        self.set_verbosity(4)
        from player import HoldBot
        self.connect_server([HoldBot] * 7, 2)

if __name__ == '__main__': unittest.main()

# vim: sts=4 sw=4 et tw=75 fo=crql1
