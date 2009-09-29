r'''Parlance game watchers
    Copyright (C) 2004-2009  Eric Wald
    
    This module creates classes to listen in on all messages from all games.
    Such classes may implement ratings ladders or abuse monitors.
    They normally wouldn't actually interact with the clients.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

from __future__ import division

from cPickle import dump, load
from os import path

from parlance.config import VerboseObject
from parlance.tokens import HUH, NOT, REJ, YES
from parlance.util import s

class Watcher(VerboseObject):
    r'''Game message watcher.
        Contains simple handlers to pass messages to any handler methods
        defined in subclasses.  More functionality may be included if deemed
        worthwhile to several watchers.
    '''#'''
    
    def handle_broadcast_message(self, message, game):
        r'''Process a message sent from the server to all clients.
            The game parameter will be either None or a game name.
            Currently, only OFF and ADM can be broadcast without a game.
        '''#'''
        self.handle_message("handle_broadcast", message, game)
    
    def handle_server_message(self, message, game, recipient):
        r'''Process a message sent from the server to a client.
            The game parameter will be a game name.
            The recipient parameter will be a client id.
        '''#'''
        self.handle_message("handle_server", message, game, recipient)
    
    def handle_client_message(self, message, game, sender):
        r'''Process message sent from a client to the server.
            The game parameter will be a game name.
            The sender parameter will be a client id.
        '''#'''
        self.handle_message("handle_client", message, game, sender)
    
    def handle_message(self, prefix, message, *args):
        r'''Dispatch a message to the appropriate handler.
            Hands it off to a handle_sender_XXX() method, where sender is
            either "client" or "server", and XXX is the first token of the
            message, if such a method is defined.  HUH, YES, REJ, and NOT
            messages are instead passed to handle_sender_XXX_YYY(), where
            YYY is the first token in the submessage.
        '''#'''
        parts = [prefix, message[0].text]
        
        # Special handling for common prefixes
        if message[0] in (YES, REJ, NOT, HUH):
            parts.append(message[2].text)
        
        method_name = str.join("_", parts)
        
        # Note that try: / except AttributeError: isn't appropriate here,
        # because the method calls might produce AttributeErrors.
        method = getattr(self, method_name, None)
        if method:
            self.log.debug("%s(%s, *%s)", method.__name__, message, args)
            try:
                method(message, *args)
            except Exception:
                self.log.exception("Exception handling %s", message)

class Ladder(Watcher):
    r'''A simple watcher to implement a ratings ladder.
        This ladder uses a zero-sum system where a win is worth (N/M - 1)
        points, while a loss is worth -1 point, where N is the number of
        players and M is the number of participants in a draw, or 1 for
        a solo.  For example, in a 7-player game, a solo is worth 6 points,
        while a 4-way draw is worth 0.75 points.
    '''#"""#'''
    __options__ = (
        ('score_file', file, path.join('log', 'stats', 'ladder_scores'),
            'ratings ladder score file',
            'The file in which to store scores generated by the Ladder observer.'),
    )
    
    def __init__(self, **kwargs):
        self.__super.__init__(**kwargs)
        self.log.debug("Using score file %s", self.options.score_file)
        self.winners = {}
    
    def handle_broadcast_DRW(self, message, game):
        if len(message) > 3:
            self.winners[game] = set(message[2:-1])
        else:
            self.winners[game] = set()
    def handle_broadcast_SLO(self, message, game):
        self.winners[game] = set([message[2]])
    
    def handle_broadcast_SMR(self, message, game):
        # Don't count games that ended without a conclusion.
        if self.winners.get(game) is not None:
            players, winners = self.collect_stats(message, game)
            if winners:
                self.record_stats(players, winners)
    def collect_stats(self, message, game):
        # Todo: Account for replacements properly.
        # That requires the starting year, unfortunately.
        seen = set()
        players = []
        survivors = set()
        for row in message.fold()[2:]:
            power, name, version = row[:3]
            if power not in seen:
                players.append((power, name[0], version[0], 1))
                seen.add(power)
            
            if not row[4:]:
                # Neither eliminated nor replaced
                survivors.add(power)
        
        winners = self.winners[game] or survivors
        del self.winners[game]  # Avoid leaking memory
        return players, winners
    
    def record_stats(self, players, winners):
        # This method may be overridden to implement other scoring systems.
        win_points = (len(players) / len(winners)) - 1
        loss_points = -1
        
        scores = self.read_scores()
        self.log.debug("Initial scores: %r", dict(scores))
        
        # Scoring loop
        for power, name, version, factor in players:
            key = (name, version)
            
            if power in winners:
                diff = win_points
            else: diff = loss_points
            diff *= factor
            scores[key] = scores.get(key, 0) + diff
            
            if diff < 0:
                gain = 'loses'
            else: gain = 'gains'
            
            change = abs(diff)
            self.log.info("%s (%s) %s %g point%s, for a total of %g."
                % (name, version, gain, change, s(change), scores[key]))
        
        self.store_scores(scores)
    
    # Score storage system
    # Todo: Switch to a real database
    def read_scores(self):
        try:
            stream = open(self.options.score_file)
        except IOError:
            self.log.warning("Failed to open the score file for reading.")
            result = {}
        else:
            result = load(stream)
            if not isinstance(result, dict):
                self.log.warning("Score file did not contain a pickled dictionary.")
                result = {}
            stream.close()
        return result
    def store_scores(self, scores):
        try:
            stream = open(self.options.score_file, 'w')
        except IOError:
            self.log.warning("Failed to open the score file for writing.")
        else:
            dump(scores, stream)
            stream.close()
