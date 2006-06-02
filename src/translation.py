''' PyDip text-to-tokens translation
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
'''#'''

from functions import Verbose_Object
from language import IntegerToken, Message, StringToken, Token

__all__ = ['Representation', 'translate', 'read_message_file']

# Temporary stubs while I get this sorted out
def read_message_file(filename, rep=None):
    ''' Reads a Diplomacy message written in a text file.
        >>> msg = read_message_file('variants/standard.sco', default_rep)
        >>> msg.fold()[2]
        [ENG, LVP, EDI, LON]
    '''#'''
    from config import protocol
    return (rep or protocol.base_rep).read_message_file(filename)

def translate(text, rep=None):
    ''' Translates a diplomacy message string into a Message.'''
    from config import protocol
    return (rep or protocol.base_rep).translate(text)

class Representation(Verbose_Object):
    ''' Holds and translates all tokens for a variant.
        Warning: Abuses the traditional dict methods.
    '''#'''
    def __init__(self, tokens, base):
        from config import token_options
        # tokens is a number -> name mapping
        self.opts = token_options()
        self.base = base
        self.names = names = {}
        self.numbers = nums = {}
        for number, name in tokens.iteritems():
            nums[number] = names[name] = Token(name, number)
    
    def __getitem__(self, key):
        ''' Returns a Token from its name or number.'''
        result = self.get(key)
        if not result:
            if isinstance(key, int): key = '0x%04X' % key
            raise KeyError, 'unknown token %r' % (key,)
        return result
    def get(self, key, default=None):
        ''' Returns a Token from its name or number.
            >>> default_rep.get('ITA')
            ITA
        '''#'''
        result = self.numbers.get(key) or self.names.get(key)
        if not result:
            if isinstance(key, Token): result = key
            elif self.base: result = self.base.get(key)
            else:
                try: number = int(key)
                except ValueError: result = default
                else:
                    if number < self.opts.max_neg_int:
                        result = IntegerToken(number)
                    elif (number & 0xFF00) == self.opts.quot_prefix:
                        result = StringToken(chr(number & 0x00FF))
                    elif self.opts.ignore_unknown:
                        result = Token('0x%04X' % number, number)
                    else: raise ValueError, 'unknown token number 0x%04X' % number
        return result or default
    
    def has_key(self, key):
        ''' Determines whether a given TLA is in use.'''
        return ((key in self.names) or (key in self.numbers) or
                (self.base and self.base.has_key(key)))
    
    def __len__(self):
        return len(self.numbers)
    
    def items(self):
        ''' Creates a name -> token mapping.'''
        return self.names.items()
    
    def keys(self):
        ''' Returns a list of token TLAs.'''
        return self.names.keys()
    
    def read_message_file(self, filename):
        ''' Reads a Diplomacy message written in a text file.
            >>> msg = default_rep.read_message_file('variants/standard.sco')
            >>> msg.fold()[2]
            [ENG, LVP, EDI, LON]
        '''#'''
        message_file = open(filename, 'r', 1)
        text = str.join(' ', message_file.readlines())
        message_file.close()
        return self.translate(text)
    
    def translate(self, text):
        ''' Translates diplomacy message strings into Messages,
            choosing an escape model based on options.
            
            # Black magic: This test exploits an implementation detail or two.
            # This test avoids backslashes because they get halved too often.
            >>> s = 'NME("name^""KET""BRA"KET""BRA" ^")'
            >>> default_rep.opts.input_escape = '"'
            >>> str(default_rep.translate(s))
            'NME ( "name^""KET""BRA" ) ( " ^" )'
            >>> default_rep.opts.input_escape = '^'
            >>> str(default_rep.translate(s))
            Traceback (most recent call last):
                ...
            KeyError: 'unknown token \\'"\\''
        '''#'''
        if self.opts.input_escape == self.opts.quot_char:
            return self.translate_doubled_quotes(text)
        else: return self.translate_backslashed(text)
    
    def translate_doubled_quotes(self, text):
        ''' Translates diplomacy message strings into Messages,
            doubling quotation marks to escape them.
            
            >>> default_rep.opts.input_escape = '"'
            >>> default_rep.translate_doubled_quotes('NOT ( GOF KET')
            Message([NOT, [GOF]])
            >>> str(default_rep.translate_doubled_quotes('      REJ(NME ("Evil\\'Bot v0.3\\r"KET(""")\\n (\\\\"-3)\\r\\n'))
            'REJ ( NME ( "Evil\\'Bot v0.3\\r" ) ( """)\\n (\\\\" -3 )'
            >>> default_rep.translate_doubled_quotes('YES " NOT ')
            Traceback (most recent call last):
                ...
            ValueError: unterminated string in Diplomacy message
        '''#'''
        # initialization
        fragments = text.split(self.opts.quot_char)
        message = []
        in_text = 0
        
        # aliases
        quoted = self.tokenize_quote
        normal = self.tokenize_normal
        addmsg = message.extend
        append = message.append
        
        # The first normal part might be empty (though it shouldn't),
        # so we process it here instead of inside the loop.
        addmsg(normal(fragments[0]))
        
        # Empty normal parts in the middle are really pairs of quotation marks
        for piece in fragments[1:-1]:
            in_text = not in_text
            if in_text: addmsg(quoted(piece))
            elif piece: addmsg(normal(piece))
            else: append(StringToken(self.opts.quot_char))
        
        # Again, the last normal part might be empty.
        if len(fragments) > 1:
            in_text = not in_text
            if in_text: addmsg(quoted(fragments[-1]))
            else:       addmsg(normal(fragments[-1]))
        
        # Complain if the message wasn't finished
        if in_text: raise ValueError, 'unterminated string in Diplomacy message'
        else: return Message(message)
    
    def translate_backslashed(self, text):
        ''' Translates diplomacy message strings into Messages,
            using backslashes to escape quotation marks.
            
            >>> default_rep.opts.input_escape = '\\\\'
            >>> default_rep.translate_backslashed('NOT ( GOF KET')
            Message([NOT, [GOF]])
            >>> str(default_rep.translate_backslashed('     REJ(NME ("Evil\\'Bot v0.3\\r"KET("\\\\")\\n (\\\\\\\\"-3)\\r\\n'))
            'REJ ( NME ( "Evil\\'Bot v0.3\\r" ) ( """)\\n (\\\\" -3 )'
            >>> default_rep.translate_backslashed('YES " NOT ')
            Traceback (most recent call last):
                ...
            ValueError: unterminated string in Diplomacy message
        '''#'''
        
        # initialization
        fragments = text.split(self.opts.quot_char)
        message = []
        in_text = False
        saved = ''
        slash = self.opts.input_escape
        
        # aliases
        quoted = self.tokenize_quote
        normal = self.tokenize_normal
        addmsg = message.extend
        
        # Empty normal parts in the middle are really pairs of quotation marks
        for piece in fragments:
            slashes = 0
            while piece and (piece[-1] == slash):
                piece = piece[:-1]
                slashes += 1
            piece += slash * int(slashes/2)
            
            if slashes % 2:
                # Odd number: escape the quotation mark
                saved += piece + self.opts.quot_char
            else:
                if in_text: addmsg(quoted(saved + piece))
                else:       addmsg(normal(saved + piece))
                in_text = not in_text
                saved = ''
        
        # Complain if the message wasn't finished
        if saved or not in_text:
            raise ValueError, 'unterminated string in Diplomacy message'
        else: return Message(message)
    
    def tokenize_quote(self, text):
        ''' Returns a list of tokens from a string within a quotation.
            >>> default_rep.tokenize_quote('Not(Gof)')
            [StringToken('N'), StringToken('o'), StringToken('t'), StringToken('('), StringToken('G'), StringToken('o'), StringToken('f'), StringToken(')')]
            >>> default_rep.tokenize_quote('name')
            [StringToken('n'), StringToken('a'), StringToken('m'), StringToken('e')]
        '''#'''
        return [StringToken(c) for c in text]
    
    def tokenize_normal(self, text):
        ''' Returns a list of tokens from a string without quotations.
            >>> default_rep.tokenize_normal('Not(Gof)')
            [NOT, BRA, GOF, KET]
            >>> default_rep.tokenize_normal('name')
            Traceback (most recent call last):
                ...
            KeyError: "unknown token 'NAME'"
        '''#'''
        # Switch parentheses to three-character notation
        text = text.replace('(', ' BRA ')
        text = text.replace(')', ' KET ')
        
        # Pass items into Token, converting integers if necessary
        return [self[maybe_int(word.upper())] for word in text.split()]

def maybe_int(word):
    ''' Converts a string to an int if possible.
        Returns either the int, or the original string.
        >>> [(type(x), x) for x in [maybe_int('-3'), maybe_int('three')]]
        [(<type 'int'>, -3), (<type 'str'>, 'three')]
    '''#'''
    try:    n = int(word)
    except: return word
    else:   return n

class RawClient(Verbose_Object):
    ''' Simple client to translate DM to and from text.'''
    name = None
    def __init__(self, send_method, representation, **kwargs):
        self.send_out  = send_method      # A function that accepts messages
        self.rep       = representation   # The representation message
        self.closed    = False # Whether the connection has ended, or should end
        self.manager   = kwargs.get('manager')
    def register(self):
        from network import InputWaiter
        print 'Connected.'
        self.manager.add_polled(InputWaiter(self.handle_input, self.close))
    def handle_message(self, message):
        ''' Process a new message from the server.'''
        print '>>', message
    def close(self):
        ''' Informs the player that the connection has closed.'''
        print 'Closed.'
        self.closed = True
        if not self.manager.closed: self.manager.close()
    def handle_input(self, line):
        try: message = self.rep.translate(line)
        except Exception, err: print str(err) or '??'
        else: self.send(message)
    def send(self, message):
        if not self.closed: self.send_out(message)

if __name__ == '__main__':
    from main import run_player
    run_player(RawClient, False, False)
