r'''Announcer - A Parlance observer to advertise games to a mailing list.
    While the game is forming, it will send "HAVE 3 NEED 4" emails;
    when the game is done, it will send a summary of the results.
'''#"""#'''

import re
from warnings import warn

from parlance.config import Configuration
from parlance.player import Observer
from parlance.tokens import SEL

def email(value):
    # Verifies that the value looks like an email address
    # Very basic regular expression; see
    # http://nedbatchelder.com/blog/200908/humane_email_validation.html
    if not re.match(r"^[^@ ]+@[^@ ]+\.[^@ ]+$", value):
        warn("Invalid email address")
    return value

class Announcer(Observer):
    have_need = re.compile("Have (\d+) player.*Need (\d+) to start")
    
    __section__ = "announcer"
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
        self.announced = 0
        self.host = Configuration.get("socket.host", "")
        if self.host:
            port = Configuration.get("socket.port")
            if port: self.host += ":" + str(port)
        
        if not self.game_id:
            self.send(+SEL)
    
    def handle_ADM(self, message):
        if self.options.recruit_address:
            line = message.fold()[2][0]
            match = self.have_need.search(line)
            if match:
                have, need = map(int, match.groups())
                if have != self.announced:
                    self.recruit(have, need)
                    self.announced = have
    def recruit(self, have, need):
        title = "Game forming"
        if self.host: title += " at " + self.host
        subject = "%s - Have %d Need %d" % (title, have, need)
        
        body = "Please come join us!"
        # Todo: Describe the game options in detail
        self.send_mail(self.options.recruit_address, subject, body)
    
    def game_over(self, message):
        self.result = message
    handle_DRW = game_over
    handle_SLO = game_over
    
    def handle_SMR(self, message):
        if self.options.result_address:
            subject = "Results"
            if self.game_id:
                subject += " for " + str(self.game_id)
            
            # Todo: Humanize these messages
            body = "\n".join([
                "Result: " + str(self.result),
                "Summary: " + str(message),
            ])
            
            self.send_mail(self.options.result_address, subject, body)
        self.close()
    
    def send_mail(self, address, subject, body):
        assert address
        assert subject
        assert body
        
        print "To: " + address
        print "Subject: " + subject
        print
        print body

if __name__ == "__main__":
    Announcer.main()
