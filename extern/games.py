r'''Alternative games for the Holland adaptive agents.
    Designed to test whether we have something worthwhile yet.
'''#"""#'''

import curses
import sys
from itertools import count
from parang.holland import Agent
from parlance.fallbacks import all, wraps
from parlance.util import s

class TicTacToe(object):
    symbols = [" ", "X", "O"]
    rewards = [400, 50, 900]
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
    
    def __init__(self):
        self.agent = Agent([])
        self.collect_handlers()
        self.err = None
        curses.wrapper(self.run)
        if self.err:
            e,x,c = self.err
            raise e,x,c
    
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
    
    def run(self, win):
        try:
            self.win = win
            self.start()
            
            self.goto(1, 1)
            done = False
            while not done:
                self.goto(*self.pos)
                win.refresh()
                key = win.getkey()
                #self.output("%r", key)
                handler = self.handlers.get(key)
                if handler:
                    done = handler()
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
        self.player = 1
        
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
        
        self.board = [0] * 9
        blank = self.symbols[0]
        for x in self.cols:
            for y in self.rows:
                win.addch(y, x, blank)
    
    def output(self, line, *args):
        if args:
            line %= args
        y, x = self.outpos
        self.win.addstr(y, x, line)
        self.win.clrtoeol()
    
    def goto(self, row, col):
        self.win.move(self.rows[row], self.cols[col])
        self.pos = (row, col)
    
    def handler(*keys):
        def decorator(f):
            f.input_keys = keys
            return f
        return decorator
    
    def movement(f):
        dy, dx = f()
        @wraps(f)
        def move(self):
            y = (self.pos[0] + dy) % 3
            x = (self.pos[1] + dx) % 3
            self.goto(y, x)
        return move
    
    @handler("KEY_UP", "k")
    @movement
    def move_up(): return -1, 0
    
    @handler("KEY_DOWN", "j")
    @movement
    def move_down(): return 1, 0
    
    @handler("KEY_LEFT", "h")
    @movement
    def move_left(): return 0, -1
    
    @handler("KEY_RIGHT", "l")
    @movement
    def move_right(): return 0, 1
    
    @handler("\n", " ", "x", "X", "o", "O")
    def select(self):
        player = self.player
        pos = self.square.index(self.pos)
        self.fill(pos, 1)
        done = self.check()
        if not done:
            self.generate()
            done = self.check()
        return done
    
    def generate(self):
        "Generate a move for the computer player."
        msg = sum(x << (n*2) for n, x in enumerate(self.board))
        for n in count(1):
            msg = self.agent.process(msg)
            pos = msg % 9
            if not self.board[pos]:
                self.output("%d round%s", n, s(n))
                break
        self.fill(pos, 2)
        self.goto(*self.square[pos])
    
    def fill(self, pos, player):
        if player != self.player:
            # No cheating!
            return False
        
        self.player ^= 3
        self.board[pos] = player
        r, c = self.square[pos]
        y = self.rows[r]
        x = self.cols[c]
        self.win.addch(y, x, self.symbols[player])
    
    def check(self):
        winner = self.winner()
        done = False
        if winner:
            self.output("Winner: %s", self.symbols[winner])
            done = True
        elif all(self.board):
            self.output("Tie!")
            done = True
        if done:
            bonus = self.rewards[winner]
            self.agent.reward(bonus)
        return done
    
    def winner(self):
        b = self.board
        result = max([b[x] & b[y] & b[z]
                for x in range(9)
                for y in range(x)
                for z in range(y)
                if x+y+z == 12])
        return result
    
    @handler("\x1b", "q")
    def exit(self):
        return True

if __name__ == "__main__":
    TicTacToe()
