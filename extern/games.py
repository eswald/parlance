r'''Alternative games for the Holland adaptive agents.
    Designed to test whether we have something worthwhile yet.
'''#"""#'''

import curses
import sys
from itertools import count
from time import sleep

from parang.holland import Agent, Classifier
from parlance.fallbacks import all, wraps
from parlance.util import s

class TicTacToe(object):
    symbols = [" ", "X", "O"]
    square = [
        (0, 1),
        (2, 0),
        (1, 2),
        (2, 2),
        (1, 1),
        (0, 0),
        (1, 0),
        (0, 2),
        (2, 1),
    ]
    
    def __init__(self, players):
        self.players = [cls(self) for cls in players]
        self.err = None
        curses.wrapper(self.run)
        if self.err:
            e,x,c = self.err
            raise e,x,c
    
    def run(self, win):
        try:
            self.win = win
            self.start()
            
            self.goto(1, 1)
            done = False
            player = 1
            while not done:
                self.turn(player)
                player ^= 3
            win.refresh()
        except:
            # Re-raise, but outside of the curses wrapper.
            self.err = sys.exc_info()
    
    def start(self):
        cx = curses.COLS // 2
        cy = curses.LINES // 2
        self.rows = [cy - 2, cy, cy + 2]
        self.cols = [cx - 4, cx, cx + 4]
        hlines = [cy - 1, cy + 1]
        vlines = [cx - 2, cx + 2]
        top, bottom = cy - 2, cy + 2
        left, right = cx - 5, cx + 5
        
        self.outpos = bottom + 3, left
        
        win = self.win
        for y in hlines:
            for x in xrange(left, right + 1):
                win.addch(y, x, curses.ACS_HLINE)
        for x in vlines:
            for y in xrange(top, bottom + 1):
                win.addch(y, x, curses.ACS_VLINE)
        for x in vlines:
            for y in hlines:
                win.addch(y, x, curses.ACS_PLUS)
        
        self.reset()
    
    def reset(self):
        self.board = [0] * 9
        
        blank = self.symbols[0]
        for x in self.cols:
            for y in self.rows:
                self.win.addch(y, x, blank)
    
    def turn(self, num):
        player = self.players[num - 1]
        self.output("Player %s", self.symbols[num])
        while True:
            self.goto(*self.pos)
            self.win.refresh()
            pos = player.generate()
            if self.board[pos] == 0:
                break
            else:
                self.output("Position %d already taken", pos)
        self.fill(pos, num)
        self.goto(*self.square[pos])
        self.check()
    
    def output(self, line, *args):
        if args:
            line %= args
        y, x = self.outpos
        self.win.addstr(y, x, line)
        self.win.clrtoeol()
    
    def goto(self, row, col):
        self.win.move(self.rows[row], self.cols[col])
        self.pos = (row, col)
    
    def check(self):
        winner = self.winner()
        done = False
        if winner:
            self.output("Winner: %s", self.symbols[winner])
            self.win.refresh()
            sleep(.2)
            done = True
            for n, player in enumerate(self.players):
                if winner == n + 1:
                    points = 1
                else:
                    points = -1
                player.result(points)
        elif all(self.board):
            self.output("Tie!")
            self.win.refresh()
            sleep(.2)
            done = True
            for player in self.players:
                player.result(0)
        if done:
            self.reset()
        return done
    
    def winner(self):
        b = self.board
        result = max([b[x] & b[y] & b[z]
                for x in range(9)
                for y in range(x)
                for z in range(y)
                if x+y+z == 12])
        return result
    
    def fill(self, pos, player):
        self.board[pos] = player
        r, c = self.square[pos]
        y = self.rows[r]
        x = self.cols[c]
        self.win.addch(y, x, self.symbols[player])
    
    def move(self, dy, dx):
        y = (self.pos[0] + dy) % 3
        x = (self.pos[1] + dx) % 3
        self.goto(y, x)

class HumanPlayer(object):
    def __init__(self, game):
        self.game = game
        self.collect_handlers()
    
    def generate(self):
        pos = None
        while pos is None:
            key = self.game.win.getkey()
            #self.output("%r", key)
            handler = self.handlers.get(key)
            if handler:
                pos = handler()
        return pos
    
    def result(self, points):
        sleep(.2)
    
    def collect_handlers(self):
        self.handlers = handlers = {}
        for name in dir(self):
            try:
                f = getattr(self, name)
                keys = f.im_func.input_keys
            except AttributeError:
                pass
            else:
                for key in keys:
                    handlers[key] = f
    
    def handler(*keys):
        def decorator(f):
            f.input_keys = keys
            return f
        return decorator
    
    @handler("KEY_UP", "k")
    def move_up(self):
        self.game.move(-1, 0)
    
    @handler("KEY_DOWN", "j")
    def move_down(self):
        self.game.move(1, 0)
    
    @handler("KEY_LEFT", "h")
    def move_left(self):
        self.game.move(0, -1)
    
    @handler("KEY_RIGHT", "l")
    def move_right(self):
        self.game.move(0, 1)
    
    @handler("\n", " ", "x", "X", "o", "O")
    def select(self):
        pos = self.game.square.index(self.game.pos)
        return pos
    
    @handler("\x1b", "q")
    def exit(self):
        sys.exit(0)

class ComputerPlayer(object):
    # Loss, Tie, Win
    rewards = [50, 400, 900]
    agent = None
    table = None
    
    def __init__(self, game):
        if not self.agent:
            self.agent = Agent(self.rules())
        self.game = game
    
    def generate(self):
        "Generate a move for the computer player."
        msg = sum(x << (n*2) for n, x in enumerate(self.game.board))
        for n in count(1):
            msg = self.agent.process(msg)
            pos = msg % 9
            if not self.game.board[pos]:
                self.game.output("%d round%s", n, s(n))
                break
        return pos
    
    def result(self, points):
        bonus = self.rewards[points + 1]
        self.agent.reward(bonus)
        self.save()
    
    def rules(self):
        try:
            from pymongo import Connection
        except ImportError:
            rules = []
        else:
            self.table = Connection().parang.tictactoe
            rules = [Classifier(row) for row in self.table.find()]
        return rules
    
    def save(self):
        # Todo: Make this more incremental
        if self.table:
            current = []
            for rule in self.agent.rules:
                uid = self.table.save(rule.values())
                current.append(uid)
            
            # Remove any deleted classifiers.
            self.table.remove({"_id": {"$nin": current}})

class BasicPlayer(object):
    def __init__(self, game):
        self.game = game
    
    def generate(self):
        return self.game.board.index(0)
    
    def result(self, points):
        pass

if __name__ == "__main__":
    TicTacToe([ComputerPlayer, ComputerPlayer])
