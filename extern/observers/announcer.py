r'''Announcer - A Parlance observer to advertise games to a mailing list.
    While the game is forming, it will send "HAVE 3 NEED 4" emails;
    when the game is done, it will send a summary of the results.
'''#"""#'''

import re
from warnings import warn

from parlance.player import Observer

def email(value):
    # Verifies that the value looks like an email address
    # Very basic regular expression; see
    # http://nedbatchelder.com/blog/200908/humane_email_validation.html
    if not re.match(r"^[^@ ]+@[^@ ]+\.[^@ ]+$", value):
        warn("Invalid email address")
    return value

class Announcer(Observer):
    have_need = re.compile("Have (\d+) player.*Need (\d+) to start")
    
    __options__ = (
        ("recruit_address", email, None, None,
            "Where to send recruitment messages."
            "Leave blank to not send them."),
        ("result_address", email, None, None,
            "Where to send results."),
    )
    
    def __init__(self, **kwargs):
        '''Initializes the instance variables.'''
        self.__super.__init__(**kwargs)
        self.quit = False
        self.result = None
        self.announced = None
        print "Recruit: " + str(self.options.recruit_address)
        print "Results: " + str(self.options.result_address)
    
    def handle_ADM(self, message):
        if self.options.recruit_address:
            line = message.fold()[2][0]
            match = self.have_need.search(line)
            if match:
                have, need = map(int, match.groups())
                if have and (have, need) != self.announced:
                    print "To: " + str(self.options.recruit_address)
                    print "HAVE %d NEED %d" % (have, need)
                    self.announced = (have, need)
    
    def game_over(self, message):
        self.result = message
    handle_DRW = game_over
    handle_SLO = game_over
    
    def handle_SMR(self, message):
        if self.options.result_address:
            print "To: " + str(self.options.result_address)
            if self.game_id: print "Game: " + str(self.game_id)
            print "Result: " + str(self.result)
            print "Summary: " + str(message)
        self.close()

if __name__ == "__main__":
    Announcer.main()
