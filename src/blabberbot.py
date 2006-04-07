''' BlabberBot - A talkative creature that makes no sense.
    Copyright (C) 2006 Eric Wald
    Licensed under the Open Software License version 3.0
'''#'''

from sets         import Set
from time         import sleep
from random       import choice, random, randrange, shuffle
from functions    import version_string
from dumbbot      import DumbBot
from language     import *

__version__ = "$Revision$"

class BlabberBot(DumbBot):
    ''' Based on the DumbBot algorithm, but sends random press messages.
        Repeatedly.  Without stop.  Especially if you try to talk to it.
    '''#'''
    
    # Items for the NME message
    name    = 'BlabberBot'
    version = version_string(__version__)
    description = 'Senseless, ceaseless ramblings'
    
    # Static variables
    print_csv = True
    
    def handle_HLO(self, message):
        self.__super.handle_HLO(message)
        me = message[2]
        if me.is_power() and self.opts.LVL >= 10:
            countries = Set(self.map.powers.keys())
            countries.remove(me)
            self.countries = list(countries)
            self.syntax = {}
            self.blab()
        else: self.close()
    def handle_FRM(self, message):
        folded = message.fold()
        sender = folded[1][0]
        press  = folded[3]
        
        replies = (YES, REJ, BWX)
        if press[0] not in replies + (HUH, TRY):
            self.send_press(sender, choice(replies)(press))
    def handle_YES_SND(self, message):
        sleep(5 + random() * 10)
        self.blab()
    def blab(self):
        self.send_press(choice(self.countries),
                self.random_expression('press_message'))
    def random_expression(self, expression):
        try: items = self.syntax[expression]
        except KeyError:
            import validation
            items = self.syntax[expression] = [syntax
                    for level, syntax in validation.syntax[expression]
                    if level <= self.opts.LVL]
        shuffle(items)
        
        result = None
        for option in items:
            result = self.random_option(option)
            if result: break
        return result
    def random_option(self, option):
        in_sub = in_cat = False
        repeat = 1
        partial = None
        msg = Message()
        for item in option:
            if isinstance(item, str):
                if item == 'repeat': repeat = 1 + randrange(4)
                elif item == 'sub': in_sub = True
                elif item == 'cat': in_cat = True
                elif item == 'optional':
                    if randrange(3): partial = Message(msg)
                    else: break
                else:
                    if in_sub:
                        # Wrapped subexpression
                        while repeat:
                            result = self.random_expression(item)
                            if result:
                                msg &= result
                                repeat -= 1
                            else: return partial
                    elif in_cat:
                        # Category name
                        while repeat:
                            result = self.random_category(item)
                            if result:
                                msg.append(result)
                                repeat -= 1
                            else: return partial
                    else:
                        # Unwrapped subexpression(s)
                        while repeat:
                            result = self.random_expression(item)
                            if result:
                                msg.extend(result)
                                repeat -= 1
                            else: return partial
                    in_sub = in_cat = False
                    repeat = 1
            elif isinstance(item, Token):
                msg.extend([item] * repeat)
                repeat = 1
        return msg
    def random_category(self, category):
        result = None
        if category == 'Powers':
            result = choice(self.map.powers.keys())
        elif category == 'Provinces':
            result = choice(self.map.spaces.keys())
        elif category == 'Integers':
            result = IntegerToken(randrange(Token.opts.max_pos_int))
        elif category == 'Phases':
            result = choice(self.map.opts.seasons)
        elif category == 'Coasts':
            result = choice([NCS, NEC, ECS, SEC])
        elif category == 'Text':
            result = StringToken(choice("'abcdefghijklmnopqrstuvwxyz "
                'ABCDEFGHIJKLMNOPQRSTUVWXYZ +-*/0123456789.?'))
        elif category[-2:] == 'SC':
            result = choice([prov for prov in self.map.spaces.keys()
                    if prov.is_supply()])
        elif category == 'Token':
            result = self.random_category(choice(['Provinces',
                'Powers', 'Phases', 'Integers', 'Coasts', 'Text']))
        return result


if __name__ == "__main__":
    import main
    main.run_player(BlabberBot)
