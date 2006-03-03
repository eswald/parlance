''' PyDip text-to-tokens translation
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
    
    Exported functions: translate(), read_message_file()
'''#'''

from language import Message, Token

__all__ = ['translate', 'read_message_file']

def read_message_file(filename, rep=None):
    ''' Reads a Diplomacy message written in a text file.
        >>> from config import default_rep
        >>> msg = read_message_file('variants/standard.sco', default_rep)
        >>> msg.fold()[2]
        [ENG, LVP, EDI, LON]
    '''#'''
    message_file = open(filename, 'r', 1)
    text = ' '.join(message_file.readlines())
    message_file.close()
    return translate(text, rep)

def translate(text, rep=None):
    ''' Translates diplomacy message strings into Messages,
        choosing an escape model based on options.
        
        # Black magic: This test exploits an implementation detail or two.
        # Note that the backslashes are halved twice,
        # so the Message really only has one in each place.
        >>> s = 'NME("name\\\\""KET""BRA"KET""BRA" \\\\")'
        >>> Token.opts.double_quotes = True;  str(translate(s))
        'NME ( "name\\\\""KET""BRA" ) ( " \\\\" )'
        >>> Token.opts.double_quotes = False; str(translate(s))
        'NME ( "name\\\\"" ) ( "KETBRA\\\\"" )'
    '''#'''
    if Token.opts.double_quotes: return translate_doubled_quotes(text, rep)
    else:                        return translate_backslashed(text, rep)

def translate_doubled_quotes(text, rep):
    ''' Translates diplomacy message strings into Messages,
        doubling quotation marks to escape them.
        
        >>> translate_doubled_quotes('NOT ( GOF KET', {})
        Message([NOT, [GOF]])
        >>> str(translate_doubled_quotes('      REJ(NME ("Evil\\'Bot v0.3\\r"KET(""")\\n (\\\\"-3)\\r\\n', {}))
        'REJ ( NME ( "Evil\\'Bot v0.3\\r" ) ( """)\\n (\\\\" -3 )'
        >>> translate_doubled_quotes('YES " NOT ', {})
        Traceback (most recent call last):
            ...
        ValueError: unterminated string in Diplomacy message
    '''#'''
    # initialization
    fragments = text.split(Token.opts.quot_char)
    message = []
    in_text = 0
    
    # aliases
    quoted = tokenize_quote
    normal = tokenize_normal
    addmsg = message.extend
    append = message.append
    
    # The first normal part might be empty (though it shouldn't),
    # so we process it here instead of inside the loop.
    addmsg(normal(fragments[0], rep))
    
    # Empty normal parts in the middle are really pairs of quotation marks
    for piece in fragments[1:-1]:
        in_text = not in_text
        if in_text: addmsg(quoted(piece))
        elif piece: addmsg(normal(piece, rep))
        else:       append(Token(Token.opts.quot_number))
    
    # Again, the last normal part might be empty.
    if len(fragments) > 1:
        in_text = not in_text
        if in_text: addmsg(quoted(fragments[-1]))
        else:       addmsg(normal(fragments[-1], rep))
    
    # Complain if the message wasn't finished
    if in_text: raise ValueError, 'unterminated string in Diplomacy message'
    else: return Message(message)

def translate_backslashed(text, rep):
    ''' Translates diplomacy message strings into Messages,
        using backslashes to escape quotation marks.
        
        >>> translate_backslashed('NOT ( GOF KET', {})
        Message([NOT, [GOF]])
        >>> str(translate_backslashed('     REJ(NME ("Evil\\'Bot v0.3\\r"KET("\\\\")\\n (\\\\\\\\"-3)\\r\\n', {}))
        'REJ ( NME ( "Evil\\'Bot v0.3\\r" ) ( """)\\n (\\\\" -3 )'
        >>> translate_backslashed('YES " NOT ', {})
        Traceback (most recent call last):
            ...
        ValueError: unterminated string in Diplomacy message
    '''#'''
    
    # initialization
    fragments = text.split(Token.opts.quot_char)
    message = []
    in_text = False
    saved = ''
    slash = '\\'
    
    # aliases
    quoted = tokenize_quote
    normal = tokenize_normal
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
            saved += piece + Token.opts.quot_char
        else:
            if in_text: addmsg(quoted(saved + piece))
            else:       addmsg(normal(saved + piece, rep))
            in_text = not in_text
            saved = ''
    
    # Complain if the message wasn't finished
    if saved or not in_text:
        raise ValueError, 'unterminated string in Diplomacy message'
    else: return Message(message)

def tokenize_quote(text):
    ''' Returns a list of tokens from a string within a quotation.
        >>> tokenize_quote('Not(Gof)')
        [Token('N'), Token('o'), Token('t'), Token('('), Token('G'), Token('o'), Token('f'), Token(')')]
        >>> tokenize_quote('name')
        [Token('n'), Token('a'), Token('m'), Token('e')]
    '''#'''
    return [Token(c) for c in text]

def tokenize_normal(text, rep):
    ''' Returns a list of tokens from a string without quotations.
        >>> tokenize_normal('Not(Gof)', {})
        [NOT, BRA, GOF, KET]
        >>> tokenize_normal('name', {})
        Traceback (most recent call last):
            ...
        ValueError: unknown token "NAME"
    '''#'''
    # Switch parentheses to three-character notation
    text = text.replace('(', ' BRA ')
    text = text.replace(')', ' KET ')
    
    # Pass items into Token, converting integers if necessary
    return [Token(maybe_int(word.upper()), rep=rep) for word in text.split()]

def maybe_int(word):
    ''' Converts a string to an int if possible.
        Returns either the int, or the original string.
        >>> [(type(x), x) for x in [maybe_int('-3'), maybe_int('three')]]
        [(<type 'int'>, -3), (<type 'str'>, 'three')]
    '''#'''
    try:    n = int(word)
    except: return word
    else:   return n
