''' EvilBot - A cheating diplomacy bot that plays multiple positions.
    
    This software may be reused for non-commercial purposes without
    charge, and without notifying the author. Use of any part of this
    software for commercial purposes without permission from the Author
    is prohibited.
'''#'''

from operator     import add
from sets         import Set
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
    friends = Set()
    static_logfile = 'logs/output_evilbot'
    print_csv = False
    
    def handle_HLO(self, message):
        print 'EvilBot takes over %s, passcode %d!' % (message[2], message[5].value())
        self.friends.add(message[2])
        super(EvilBot, self).handle_HLO(message)
    
    def handle_SCO(self, message):
        ''' Flags self-copies as friends, before setting power sizes,
            and sets appropriate draw settings.
        '''#'''
        for ally in self.friends:
            if self.map.powers[ally].units: self.attitude[ally] = -.1
            else: self.attitude[ally] = 2
        self.draws = [self.friends & Set(self.map.current_powers())]
        super(EvilBot, self).handle_SCO(message)


if __name__ == "__main__":
    import main
    main.run_player(EvilBot)

# vim: sts=4 sw=4 et tw=75 fo=crql1
