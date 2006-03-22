''' PyDip text-to-tokens translation
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
'''#'''

from functions import Verbose_Object
from language import Message, Token

__all__ = ['Representation', 'translate', 'read_message_file']

# Temporary stubs while I get this sorted out
def read_message_file(filename, rep=None):
    ''' Reads a Diplomacy message written in a text file.
        >>> from config import default_rep
        >>> msg = read_message_file('variants/standard.sco', default_rep)
        >>> msg.fold()[2]
        [ENG, LVP, EDI, LON]
    '''#'''
    return Representation(rep).read_message_file(filename)

def translate(text, rep=None):
    ''' Translates diplomacy message strings into Messages,
        choosing an escape model based on options.
        
        # Black magic: This test exploits an implementation detail or two.
        # Note that the backslashes are halved twice,
        # so the Message really only has one in each place.
        >>> s = 'NME("name\\\\""KET""BRA"KET""BRA" \\\\")'
        >>> Token.opts.escape_char = '"';  str(translate(s))
        'NME ( "name\\\\""KET""BRA" ) ( " \\\\" )'
        >>> Token.opts.escape_char = '\\\\'; str(translate(s))
        'NME ( "name\\\\"" ) ( "KETBRA\\\\"" )'
    '''#'''
    return Representation(rep).translate(text)

class Representation(Verbose_Object):
    ''' Holds and translates all tokens for a variant.'''
    def __init__(self, tokens):
        self.rep = tokens
        self.opts = Token.opts
    
    def read_message_file(self, filename):
        ''' Reads a Diplomacy message written in a text file.
            >>> from config import default_rep
            >>> rep = Representation(default_rep)
            >>> msg = rep.read_message_file('variants/standard.sco')
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
            # Note that the backslashes are halved twice,
            # so the Message really only has one in each place.
            >>> from config import default_rep
            >>> rep = Representation(default_rep)
            >>> s = 'NME("name\\\\""KET""BRA"KET""BRA" \\\\")'
            >>> rep.opts.escape_char = '"'
            >>> str(rep.translate(s))
            'NME ( "name\\\\""KET""BRA" ) ( " \\\\" )'
            >>> rep.opts.escape_char = '\\\\'
            >>> str(rep.translate(s))
            'NME ( "name\\\\"" ) ( "KETBRA\\\\"" )'
        '''#'''
        if self.opts.escape_char == self.opts.quot_char:
            return self.translate_doubled_quotes(text)
        else: return self.translate_backslashed(text)
    
    def translate_doubled_quotes(self, text):
        ''' Translates diplomacy message strings into Messages,
            doubling quotation marks to escape them.
            
            >>> from config import default_rep
            >>> rep = Representation(default_rep)
            >>> rep.opts.escape_char = '"'
            >>> rep.translate_doubled_quotes('NOT ( GOF KET')
            Message([NOT, [GOF]])
            >>> str(rep.translate_doubled_quotes('      REJ(NME ("Evil\\'Bot v0.3\\r"KET(""")\\n (\\\\"-3)\\r\\n'))
            'REJ ( NME ( "Evil\\'Bot v0.3\\r" ) ( """)\\n (\\\\" -3 )'
            >>> rep.translate_doubled_quotes('YES " NOT ')
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
            else:       append(Token(self.opts.quot_number))
        
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
            
            >>> from config import default_rep
            >>> rep = Representation(default_rep)
            >>> rep.opts.escape_char = '"'
            >>> rep.translate_backslashed('NOT ( GOF KET')
            Message([NOT, [GOF]])
            >>> str(rep.translate_backslashed('     REJ(NME ("Evil\\'Bot v0.3\\r"KET("\\\\")\\n (\\\\\\\\"-3)\\r\\n'))
            'REJ ( NME ( "Evil\\'Bot v0.3\\r" ) ( """)\\n (\\\\" -3 )'
            >>> rep.translate_backslashed('YES " NOT ')
            Traceback (most recent call last):
                ...
            ValueError: unterminated string in Diplomacy message
        '''#'''
        
        # initialization
        fragments = text.split(self.opts.quot_char)
        message = []
        in_text = False
        saved = ''
        slash = '\\'
        
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
            >>> from config import default_rep
            >>> rep = Representation(default_rep)
            >>> rep.tokenize_quote('Not(Gof)')
            [Token('N'), Token('o'), Token('t'), Token('('), Token('G'), Token('o'), Token('f'), Token(')')]
            >>> rep.tokenize_quote('name')
            [Token('n'), Token('a'), Token('m'), Token('e')]
        '''#'''
        return [Token(c) for c in text]
    
    def tokenize_normal(self, text):
        ''' Returns a list of tokens from a string without quotations.
            >>> from config import default_rep
            >>> rep = Representation(default_rep)
            >>> rep.tokenize_normal('Not(Gof)')
            [NOT, BRA, GOF, KET]
            >>> rep.tokenize_normal('name')
            Traceback (most recent call last):
                ...
            ValueError: unknown token "NAME"
        '''#'''
        # Switch parentheses to three-character notation
        text = text.replace('(', ' BRA ')
        text = text.replace(')', ' KET ')
        
        # Pass items into Token, converting integers if necessary
        return [Token(maybe_int(word.upper()), rep=self.rep) for word in text.split()]

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
        from threading import Thread
        self.send_out  = send_method      # A function that accepts messages
        self.rep       = representation   # The representation message
        self.closed    = False # Whether the connection has ended, or should end
        Thread(target=self.run).start()
    def handle_message(self, message):
        ''' Process a new message from the server.'''
        print '>>', message
    def close(self):
        ''' Informs the player that the connection has closed.'''
        self.closed = True
    def run(self):
        from translation import translate
        print 'Connected.'
        while not self.closed:
            try: line = raw_input()
            except EOFError: self.close()
            if line:
                try: message = translate(line, self.rep)
                except: print '??'
                self.send(message)
    def send(self, message):
        if not self.closed: self.send_out(message)

if __name__ == "__main__":
    from main import run_player
    run_player(RawClient, False, False)
