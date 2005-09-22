from player    import Observer
from threading import Thread

class Chatty(Observer):
    ''' An observer that simply lets a human chat with Admin messages.'''
    def __init__(self, *args):
        self.name = raw_input('Name: ')
        self.__super.__init__(*args)
        self.quit = False
        Thread(target=self.run).start()
    def open(self):
        self.output('Connecting...')
        return self.__super.open()
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
except ImportError:
    Cursed = Chatty
    MapChat = Chatty
else:
    class Cursed(Chatty):
        ''' A slightly better interface for the simple admin chat.'''
        def __init__(self, *args):
            self.outwin = None
            self.chatbuf = []
            self.__super.__init__(*args)
        def run(self):
            curses.wrapper(self.run_curses)
            self.close()
        def run_curses(self, win):
            self.setup_win(win)
            self.editwin = win.subwin(1, curses.COLS - 1, curses.LINES - 1, 0)
            editpad = Textbox(self.editwin)
            try:
                while not self.closed:
                    line = editpad.edit()
                    self.editwin.erase()
                    if line: self.send_admin(line)
                self.output('Goodbye, %s.', self.name)
            except EOFError: self.output('Thank you for playing.')
        def setup_win(self, win):
            win.scrollok(True)
            win.idlok(True)
            win.setscrreg(0, curses.LINES - 2)
            win.addstr(curses.LINES - 2, 0, '\n'.join(self.chatbuf))
            win.refresh()
            self.outwin = win
            self.chatbuf = []
        def output(self, line, *args):
            text = str(line) % args
            if self.outwin:
                self.outwin.addstr('\n' + text)
                self.outwin.refresh()
                self.editwin.refresh()
            else:
                print text
                self.chatbuf.append(text)
        def handle_OFF(self, message):
            self.output('The server has closed.')
            self.__super.handle_OFF(message)
    class MapChat(Cursed):
        ''' Even better: This one displays a map.'''
        def __init__(self, *args):
            self.__super.__init__(*args)
            self.use_map = True
            self.mapwin = None
            self.units = {}
        def handle_MAP(self, message):
            from config      import find_variant_file
            from translation import read_message_file
            from language    import NOW, SCO
            self.__super.handle_MAP(message)
            if self.map.valid:
                mapname = self.map.name
                filename = 'map for ' + mapname
                message = None
                try:
                    filename = find_variant_file(mapname, 'map')
                    message = read_message_file(filename, self.rep)
                    if message: self.show_map(message)
                    else: self.output('Invalid message file %s', filename)
                except Exception, e:
                    self.output('Error reading %s: %s', filename, e)
                # Just in case it works...
                self.send(NOW())
                self.send(SCO())
        def show_map(self, message):
            from language import Token
            self.init_colors()
            folded = message.fold()
            lines = [item[0] for item in folded[2]]
            length = len(lines)
            if self.outwin:
                # Todo: Consider making this a panel
                self.outwin.setscrreg(length, curses.LINES - 2)
                win = self.outwin.subwin(length, curses.COLS - 1, 0, 0)
                for y, line in enumerate(lines):
                    x = 0
                    length = len(line)
                    while x < length:
                        n = 1
                        while x+n < length and line[x+n] == line[x]: n += 1
                        color = (ord(line[x]) - ord('0')) % 8
                        win.addstr(y, x, ' '*n, self.get_color(color, color, False))
                        x += n
                    win.clrtoeol()
                
                for country in folded[0]:
                    power = self.map.powers.get(country[0])
                    if power:
                        power.__color = country[1]
                        power.__name  = country[2][0]
                        power.__adj   = country[2][0]
                for prov in folded[1]:
                    province = self.map.spaces[prov[0]]
                    province.__color = prov[1]
                    province.__name  = prov[-1][0]
                    color = self.get_color(0, province.__color, False)
                    win.addstr(prov[2], prov[3], prov[0].text, color)
                    if province.is_supply():
                        # Just received the MAP; no SCO yet.
                        #power = province.owner
                        #if power: color = self.get_color(power.__color, province.__color, True)
                        province.__x = prov[3] - 1
                        province.__y = prov[2]
                        win.addstr(province.__y, province.__x, '*', color)
                    coords = {}
                    for loc in prov[4:-1]:
                        if isinstance(loc[0], Token):
                            unit_type = loc[0]
                            coastline = None
                        else:
                            unit_type = loc[0][0]
                            coastline = loc[0][1]
                            # Label multi-coast provinces
                            win.addstr(loc[1], loc[2], coastline.text[0].lower(), color)
                        coords[(unit_type, coastline)] = loc[1:5]
                    for coast in province.coasts:
                        loc = coords[(coast.unit_type, coast.coastline)]
                        coast.__y, coast.__x, coast.__ry, coast.__rx = loc
                win.refresh()
                self.mapwin = win
                self.output('Map: %s', self.map.name)
            else: self.output('Unable to display the map.')
        def get_color(self, fg, bg, bold):
            result = curses.color_pair(self.color_pair(fg, bg))
            if bold: result += curses.A_BOLD
            return result
        def init_colors(self):
            if curses.has_colors():
                for fg in range(8):
                    for bg in range(8):
                        n = self.color_pair(fg, bg)
                        if n: curses.init_pair(n, fg, bg)
            else:
                # Efficiency increase for color settings
                self.set_color = lambda s, fg, bg: None
                self.unset_color = lambda s: None
        def color_pair(self, fg, bg):
            # Note: Assumes 8-color fg and bg, black=0, and white=7
            return (7 - fg) + (8 * bg)
        def handle_NOW(self, message):
            win = self.mapwin
            if win:
                new_units = {}
                old_units = self.units
                for unit in self.map.units:
                    coast = unit.coast
                    fg = unit.nation.__color
                    char = coast.unit_type.text[0].lower()
                    
                    if unit.dislodged:
                        x = coast.__rx
                        y = coast.__ry
                        bg = 0
                    else:
                        x = coast.__x
                        y = coast.__y
                        bg = coast.province.__color
                    win.addstr(y, x, char, self.get_color(fg, bg, True))
                    
                    if coast.coastline and not unit.dislodged:
                        char = coast.coastline.text[0].lower()
                    else: char = ' '
                    color = self.get_color(0, coast.province.__color, False)
                    new_units[(y,x)] = (y, x, char, color)
                    try: del old_units[(y,x)]
                    except KeyError: pass
                for item in old_units.values(): win.addstr(*item)
                self.units = new_units
                win.refresh()
                self.editwin.refresh()
        def handle_SCO(self, message):
            distrib = message.fold()[1:]
            win = self.mapwin
            if win:
                for dist in distrib:
                    power = self.map.powers.get(dist[0])
                    for prov in dist[1:]:
                        province = self.map.spaces[prov]
                        if power: color = self.get_color(power.__color, province.__color, True)
                        else:     color = self.get_color(0, province.__color, False)
                        win.addstr(province.__y, province.__x, '*', color)
                win.refresh()
            self.output('Supply Centres %s: %s',
                    self.map.current_turn, '; '.join([
                        '%s, %d' % (dist[0], len(dist) - 1)
                        for dist in distrib]))


if __name__ == "__main__":
    from main import run_player
    run_player(MapChat, False, False)

# vim: sts=4 sw=4 et tw=75 fo=crql1
