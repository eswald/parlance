''' EvilBot - A cheating diplomacy bot that plays multiple positions.
    
    This software may be reused for non-commercial purposes without
    charge, and without notifying the author. Use of any part of this
    software for commercial purposes without permission from the Author
    is prohibited.
'''#'''

from operator     import add
from sets         import Set
from iaq          import DefaultDict
from dumbbot      import DumbBot

class EvilBot(DumbBot):
    ''' Based on the DumbBot algorithm, but allies with other instances.
        Only instances created in the same program are recognized.
    '''#'''
    
    # Items for the NME message
    name    = 'EvilBot'
    version = '0.1'
    description = 'A cheating scumball'
    
    # Static variables
    friend_sets = DefaultDict(Set())
    print_csv = False
    
    def __init__(self, *args, **kwargs):
        self.__super.__init__(*args, **kwargs)
        self.friends = self.friend_sets[kwargs.get('game_id')]
        if len(self.friends) >= 3: self.friendly = self.crazy_friendly
        if self.power: self.friends.add(self.power.key)
        EvilBot.laughs = 3
    def handle_HLO(self, message):
        print 'EvilBot takes over %s, passcode %d!' % (message[2], message[5].value())
        self.friends.add(message[2])
        super(EvilBot, self).handle_HLO(message)
    def crazy_friendly(self, nation): return nation.key in self.friends
    
    def handle_SCO(self, message):
        ''' Flags self-copies as friends, before setting power sizes,
            and sets appropriate draw settings.
        '''#'''
        for ally in self.friends:
            if self.map.powers[ally].units: self.attitude[ally] = -.1
            else: self.attitude[ally] = 2
        self.draws = [self.friends & Set(self.map.current_powers())]
        super(EvilBot, self).handle_SCO(message)
    def handle_DRW(self, message):
        '''Laugh at the poor humans.'''
        if self.power.units: self.admin('Bwa' + '-ha' * EvilBot.laughs + '!')
        EvilBot.laughs += 1
    def handle_SLO(self, message):
        if message[2] == self.power:
            self.admin('You insignificant fools!')
            self.admin('Did you honestly think you could overcome the power of the dark side?')
    def handle_OFF(self, message):
        self.friends.remove(self.power.key)
        self.__super.handle_OFF(message)


if __name__ == "__main__":
    import main
    main.run_player(EvilBot)

# vim: sts=4 sw=4 et tw=75 fo=crql1
