r'''Test cases for the Parlance watchers
    Copyright (C) 2009  Eric Wald
    
    This module tests the server's ability to use Watchers,
    and the functionality of any Watchers included in Parlance.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

from __future__ import division

import unittest
from mock import Mock, patch

import parlance.server
from parlance.tokens import DRW, PNG, SLO, SMR, SPR, YES
from parlance.watcher import Ladder, Watcher
from parlance.xtended import AUS, ENG, FRA, GER, ITA, RUS, TUR
from parlance.test.server import ServerTestCase

class ServerWatchers(ServerTestCase):
    r'''Test cases for the Watcher interface.'''
    def new_watcher(self):
        if not self.server:
            self.connect_server()
        watcher = Mock(spec=Watcher)
        self.server.watchers = [watcher]
        return watcher
    
    @patch("parlance.server.watchers", {"watcher": Mock()})
    def test_install_watchers(self):
        self.connect_server()
        expected = [parlance.server.watchers["watcher"]()]
        self.assertEqual(self.server.watchers, expected)
    def test_broadcast_all(self):
        watcher = self.new_watcher()
        self.server.broadcast(YES (PNG))
        watcher.handle_broadcast_message.assert_called_with(YES (PNG), None)
        self.assertFalse(watcher.handle_server_message.called)
        self.assertFalse(watcher.handle_client_message.called)
    def test_broadcast_game(self):
        watcher = self.new_watcher()
        self.game.broadcast(YES (PNG))
        watcher.handle_broadcast_message.assert_called_with(YES (PNG),
            self.game.game_id)
        self.assertFalse(watcher.handle_server_message.called)
        self.assertFalse(watcher.handle_client_message.called)
    def test_server(self):
        self.connect_server()
        player = self.connect_player(self.Fake_Player)
        key = self.server.clients.keys()[0]
        client = self.server.clients[key]
        watcher = self.new_watcher()
        client.send(YES (PNG))
        
        watcher.handle_server_message.assert_called_with(YES (PNG),
            self.game.game_id, key)
        self.assertFalse(watcher.handle_broadcast_message.called)
        self.assertFalse(watcher.handle_client_message.called)
    def test_client(self):
        self.connect_server()
        player = self.connect_player(self.Fake_Player)
        key = self.server.clients.keys()[0]
        watcher = self.new_watcher()
        player.send(YES (PNG))
        
        watcher.handle_client_message.assert_called_with(YES (PNG),
            self.game.game_id, key)
        self.assertFalse(watcher.handle_broadcast_message.called)
        self.assertFalse(watcher.handle_server_message.called)

class TestLadder(unittest.TestCase):
    def new_ladder(self, scores=None):
        if scores is None:
            scores = {}
        ladder = Ladder()
        ladder.read_scores = Mock(return_value=scores)
        ladder.store_scores = Mock()
        return ladder
    
    def test_dias_draw(self):
        ladder = self.new_ladder()
        ladder.handle_broadcast_message(+DRW, "game")
        self.assertEqual(ladder.winners, {"game": set()})
    def test_pda_draw(self):
        ladder = self.new_ladder()
        ladder.handle_broadcast_message(DRW (AUS, ENG, FRA), "game")
        self.assertEqual(ladder.winners, {"game": set([AUS, ENG, FRA])})
    def test_solo(self):
        ladder = self.new_ladder()
        ladder.handle_broadcast_message(SLO (FRA), "game")
        self.assertEqual(ladder.winners, {"game": set([FRA])})
    def test_summary(self):
        winners = set([ENG, RUS])
        players = []
        starting = {}
        ending = {}
        for n, power in enumerate([AUS, ENG, FRA, GER, ITA, RUS, TUR]):
            name = str(power)
            version = "Parlance Testing"
            key = (name, version)
            score = n - 2
            if score:
                starting[key] = score
            
            row = [power, [name], [version]]
            if power in winners:
                row.append(17)
                score += 2.5
            else:
                row.append(0)
                row.append(1910)
                score -= 1
            
            players.append(row)
            ending[key] = score
        
        ladder = self.new_ladder(starting)
        ladder.winners = {"game": winners}
        ladder.handle_broadcast_message(SMR (SPR, 1910) % players, "game")
        ladder.store_scores.assert_called_with(ending)

if __name__ == '__main__': unittest.main()
