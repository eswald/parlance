from player    import Observer
from threading import Thread

class Chatty(Observer):
    ''' An observer that simply lets a human chat with Admin messages.'''
    def __init__(self, *args):
        self.name = raw_input('Name: ')
        self.__super.__init__(*args)
        self.quit = False
        Thread(target=self.run).start()
    def run(self):
        try:
            while not self.closed:
                line = raw_input()
                self.send_admin(line)
            self.output('Goodbye.')
        except EOFError: self.output('Thank you for playing.'); self.close()
    def output(self, line, *args): print str(line) % args
    def handle_ADM(self, message):
        msg = message.fold()
        self.output('%s: %s', msg[1][0], msg[2][0])
    def handle_SCO(self, message):
        dists = message.fold()[1:]
        dists.sort()
        self.output('Supply Centres: ' + '; '.join(
            ['%s, %d' % (dist[0], len(dist) - 1) for dist in dists]))
    def handle_DRW(self, message):
        from functions import expand_list
        if len(message) > 2:
            self.output('Draw declared among %s', expand_list(message[2:-1]))
        else: self.output('Draw declared among surviving players')
    def handle_SLO(self, message):
        self.output('Solo awarded to %s', message[2])
    def handle_SMR(self, message):
        self.output('Game ended in %s %s', message[2], message[3])
        for player in message.fold()[2:]:
            power,name,version,score = player[:4]
            line = '%s: %s (%s); %s centers' % (power,name[0],version[0],score)
            if len(player) > 4: line += ' (eliminated in %s)' % (player[4],)
            self.output(line)

try:
    import curses
    from curses.textpad import Textbox
    class Cursed(Chatty):
        ''' A slightly better interface for the simple admin chat.'''
        def __init__(self, *args):
            self.outwin = None
            self.chatbuf = ['']
            self.__super.__init__(*args)
        def run(self):
            curses.wrapper(self.run_curses)
            self.close()
        def run_curses(self, win):
            win.scrollok(True)
            win.idlok(True)
            win.setscrreg(0, curses.LINES - 2)
            win.addstr(curses.LINES - 3, 0, '\n'.join(self.chatbuf))
            win.refresh()
            self.outwin = win
            self.chatbuf = []
            self.editwin = win.subwin(1, curses.COLS - 1, curses.LINES - 1, 0)
            editpad = Textbox(self.editwin)
            try:
                while not self.closed:
                    line = editpad.edit()
                    self.editwin.erase()
                    if line: self.send_admin(line)
                self.output('Goodbye, %s.', self.name)
            except EOFError: self.output('Thank you for playing.')
        def output(self, line, *args):
            text = str(line) % args
            if self.outwin:
                self.outwin.addstr(text + '\n')
                self.outwin.refresh()
                self.editwin.refresh()
            elif self.closed: print text
            else: self.chatbuf.insert(-1, text)
except ImportError: Cursed = Chatty


if __name__ == "__main__":
    from main import run_player
    run_player(Cursed, False, False)

# vim: sts=4 sw=4 et tw=75 fo=crql1
