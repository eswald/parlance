''' PyDip language classes
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
    
    This package is designed to be used as "from language import *"
    but only after importing config somewhere.
    Doing so will import all DCSP tokens, with upper-case names,
    including BRA ('(') and KET (')').
    It will also import the following classes:
        - Message: A list of network tokens, usually representing a diplomacy message.
        - Token: One unit of a message, containing both its name and number.
'''#'''

from functions import Verbose_Object

class Message(list):
    ''' Representation of a Diplomacy Message, as a list of Tokens.
        >>> m = Message(NOT, BRA, GOF, KET)
        >>> print m
        NOT ( GOF )
        >>> m[0]
        NOT
        >>> m[-5]
        Traceback (most recent call last):
            ...
        IndexError: list index out of range
    '''#'''
    
    def __init__(self, *message):
        ''' Creates a new message from a string or series.
            Mostly, this will be called by calling a token;
            for best results, don't use it directly.
            
            >>> str(Message(NOT, [GOF]))
            'NOT GOF'
            >>> str(Message((NOT, [GOF])))
            'NOT ( GOF )'
        '''#'''
        for item in message: list.extend(self, _tokenize(item))
    
    def validate(self, syntax_level=0, from_server=False):
        ''' Determines whether the message is syntactically valid.
            Returns False for a good message, or an error Message
            (HUH or PRN) to send to the client.
            
            # Checks unbalanced parentheses
            >>> from translation import translate
            >>> Token.opts.squeeze_parens = True
            >>> print translate("IAM(NOT").validate()
            PRN (IAM (NOT)
            >>> print translate("IAM)NOT(").validate()
            PRN (IAM) NOT ()
            >>> print translate('PRN ( IAM ( NOT )').validate()
            False
            
            # Checks syntax
            >>> print translate('WHT(YES)').validate()
            HUH (ERR WHT (YES))
            >>> print NME('name', -3).validate()
            HUH (NME ("name") (ERR -3))
            >>> print NME('name').validate()
            HUH (NME ("name") ERR)
            >>> print NME('name', 'version').validate()
            False
            
            # Checks syntax level
            >>> Eng = Token('ENG', 0x4101)
            >>> Fra = Token('FRA', 0x4102)
            >>> Peace = AND(PCE([Eng, Fra]), DRW)
            >>> print SND(1, Eng, PRP(Peace)).validate(40)
            False
            >>> m = SND(1, Eng, PRP(ORR(NOT(DRW), Peace)))
            >>> print m.validate(40)
            HUH (SND (1) (ENG) (PRP (ORR (NOT (DRW)) (ERR AND (PCE (ENG FRA)) (DRW)))))
            >>> print m.validate(100)
            False
            
            # Checks messages from server, too
            >>> msg = MAP('standard')
            >>> print msg.validate()
            HUH (MAP ERR ("standard"))
            >>> print msg.validate(0, True)
            False
            
            # Just to restore the state for other tests:
            >>> Token.opts.squeeze_parens = False
        '''#'''
        from validation import validate_expression
        
        if self.count(BRA) != self.count(KET):
            if self[0] == PRN: return False
            else: return PRN(self)
        else:
            if from_server: base_expression = 'server_message'
            else:           base_expression = 'client_message'
            index, valid = validate_expression(self, base_expression, syntax_level)
            if valid and index == len(self): return False
            else:
                if index < len(self) and self[index] == KET:
                    submsg = self[:index + 1]
                    if submsg.count(BRA) != submsg.count(KET):
                        if self[0] == PRN: return False
                        else: return PRN(self)
                result = HUH(self)
                result.insert(index + 2, ERR)
                return result
    
    def fold(self):
        ''' Folds the token into a list, with bracketed sublists as lists.
            Also converts text and number tokens to strings and integers.
            This version takes about half the time for a map definition,
            but probably a bit longer than old_fold() for simple messages.
            
            >>> NOT(GOF).fold()
            [NOT, [GOF]]
            >>> Message().fold()
            []
            >>> NME('name', -3).fold()
            [NME, ['name'], [-3]]
            >>> from translation import translate
            >>> translate('(()(()()))()').fold()
            [[[], [[], []]], []]
            >>> translate('(()()))()(()').fold()
            Traceback (most recent call last):
                ...
            ValueError: unbalanced parentheses in folded Message
            >>> translate('NOT ( GOF').fold()
            Traceback (most recent call last):
                ...
            ValueError: unbalanced parentheses in folded Message
        '''#'''
        from functions import rindex
        complaint = 'unbalanced parentheses in folded Message'
        if self.count(BRA) != self.count(KET): raise ValueError, complaint
        series = self.convert()
        while BRA in series:
            k = series.index(KET)
            try: b = rindex(series[:k], BRA)
            except ValueError: raise ValueError, complaint
            series[b:k+1] = [series[b+1:k]]
        return series
    def convert(self):
        ''' Converts a Message into a list,
            with embedded strings and tokens converted into Python values.
            
            >>> NME('version', -3).convert()
            [NME, BRA, 'version', KET, BRA, -3, KET]
        '''#'''
        result = []
        text = ''
        append = result.append
        for token in self:
            if token.is_text(): text += token.text
            else:
                if text: append(text); text = ''
                if token.is_integer(): append(token.value())
                else: append(token)
        if text: append(text)
        return result
    
    def __str__(self):
        ''' Returns a string representation of the message.
            >>> str(NOT(GOF))
            'NOT ( GOF )'
            >>> print Message((NME, ["I'm Me"]), '"Missing" field')
            NME ( "I'm Me" ) """Missing"" field"
            >>> str(Message('name'))
            '"name"'
        '''#'''
        # No, this cannot be simplified to use sum(),
        # because it relies on the __radd__() method of Token.
        from operator import add
        return reduce(add, self, '')
    def __repr__(self):
        ''' Returns a string which can be used to reproduce the message.
            Note: Can get long, if used improperly.
            
            >>> eval(repr(NOT(GOF)))
            Message([NOT, [GOF]])
            >>> eval(repr(IAM(Token('STH', 0x4101), 42)))
            Message([IAM, [Token('STH', 0x4101)], [42]])
        '''#'''
        return 'Message(' + repr(self.fold()) + ')'
    def pack(self):
        ''' Produces a string of token numbers from a Message.
            >>> print map(lambda x: hex(ord(x)), NOT(GOF).pack())
            ['0x48', '0xd', '0x40', '0x0', '0x48', '0x3', '0x40', '0x1']
        '''#'''
        from struct import pack
        return pack('!' + 'H'*len(self), *map(int, self))
    def tokenize(self): return self
    
    # Automatically translate new items into Tokens
    def append(self, value):
        ''' Adds a new token or sublist to the Message.
            >>> m = Message(NOT)
            >>> m.append(GOF)
            >>> m
            Message([NOT, GOF])
            >>> m.append('name')
            >>> str(m)
            'NOT GOF ( "name" )'
            >>> m.append([3])
            >>> str(m)
            'NOT GOF ( "name" ) ( 3 )'
        '''#'''
        try: list.append(self, Token(value))
        except ValueError: list.extend(self, _wrap(value))
    def extend(self, value):
        ''' Adds a list of new tokens to the Message, without parentheses.
            >>> m = Message(NOT)
            >>> m.extend(GOF)
            >>> str(m)
            'NOT GOF'
            >>> m.extend('name')
            >>> str(m)
            'NOT GOF "name"'
            >>> m.extend([3])
            >>> str(m)
            'NOT GOF "name" 3'
        '''#'''
        list.extend(self, _tokenize(value))
    def __add__(self, other): return Message(list.__add__(self, other))
    def __setslice__(self, from_index, to_index, value):
        ''' Replaces a portion of the Message, with Tokens.
            >>> from translation import translate
            >>> m = translate('NOT ( GOF )')
            >>> m[1:3] = [YES, 34, 'name']
            >>> str(m)
            'NOT YES 34 "name" )'
            >>> m[-3:] = REJ
            >>> str(m)
            'NOT YES 34 "na" REJ'
        '''#'''
        try: list.__setslice__(self, from_index, to_index, _tokenize(value))
        except TypeError: raise TypeError, 'must assign list (not "%s") to slice' % type(value).__name__
    def __setitem__(self, index, value):
        ''' Replaces a single Token of the Message with another Token.
            >>> m = NOT(GOF)
            >>> m[2] = DRW; print m
            NOT ( DRW )
            >>> m[-1] = 42; print m
            NOT ( DRW 42
            >>> m[3]
            Token(42)
            >>> m[-2] = [YES, KET]
            Traceback (most recent call last):
                ...
            ValueError
        '''#'''
        list.__setitem__(self, index, Token(value))
    def insert(self, index, value):
        ''' Inserts a single token into the Message.
            >>> m = HUH(WHT)
            >>> m.insert(2, ERR)
            >>> str(m)
            'HUH ( ERR WHT )'
            >>> m.insert(3, [Token('ENG', 0x4101), Token('FRA', 0x4102)])
            Traceback (most recent call last):
                ...
            ValueError
        '''#'''
        list.insert(self, index, Token(value))


class _object_Token(object):
    ''' Core for the Token class, based on an object.
        Disadvantages: Slow comparisons and other functions;
        immutabililty can be compromised.
    '''#'''
    
    # Use __slots__ to save memory, and to maintain immutability
    __slots__ = ('text', 'number', 'key')
    
    # Initialization
    def __new__(klass, key):
        self = object.__new__(klass)
        self.key = key
        self.text = key[0]
        self.number = key[1]
        return self
    
    # Basic token properties
    def __str__(self):
        ''' Returns the text given to the token when initialized.
            May or may not be the standard DCSP name.
            
            >>> str(YES)
            'YES'
            >>> str(Token(3))
            '3'
            >>> str(Token(-3))
            '-3'
            >>> South = Token("STH", 0x4101)
            >>> South
            Token('STH', 0x4101)
            >>> str(South)
            'STH'
        '''#'''
        return self.text
    def __int__(self):
        ''' Converts the token to an integer,
            resulting in the numerical DCSP value.
            
            >>> int(YES)
            18460
            >>> int(Token('PAR', 0x510A))
            20746
            >>> int(Token(0x1980))
            6528
            >>> int(Token(-3))
            16381
        '''#'''
        return self.number
    def __setattr__(self, name, value):
        ''' Prevents modification of an instance's attributes.
            This implementation depends on __slots__ to prevent new attributes.
            (But that's just a bonus of the memory-saving feature.)
            This also fails to prevent object.__setattr__(...) calls;
            any client that does so is evil and should be shot.
            
            >>> t = REJ
            >>> t.attribute = 'value'
            Traceback (most recent call last):
                ...
            AttributeError: 'Token' object has no attribute 'attribute'
            >>> t.text = 'value'
            Traceback (most recent call last):
                ...
            AttributeError: can't set attribute
        '''#'''
        if hasattr(self, name): raise AttributeError, "can't set attribute"
        else: object.__setattr__(self, name, value)
    def __delattr__(self, name):
        ''' Prevents deletion of an instance's attributes.
            >>> del REJ.text
            Traceback (most recent call last):
                ...
            AttributeError: can't delete attribute
            >>> del REJ.attribute
            Traceback (most recent call last):
                ...
            AttributeError: 'Token' object has no attribute 'attribute'
        '''#'''
        # Let getattr raise AttributeErrors for us,
        # and raise our own complaint if it doesn't.
        getattr(self, name)
        raise AttributeError, "can't delete attribute"
    
    # Comparison
    def __hash__(self):
        ''' Generic hashing function, allowing tokens to be dictionary keys.
            >>> hash(NOT) == hash(GOF)
            False
            >>> { YES : 45 }
            {YES: 45}
        '''#'''
        return hash(self.key)
    def __cmp__(self, other):
        if isinstance(other, self.__class__):
            return cmp(self.key, other.key)
        else: return NotImplemented

class _tuple_Token(tuple):
    ''' Core for the Token class, based on an tuple.
        Disadvantages: Perceived as a series,
        particularly in string substitution with %.
    '''#'''
    
    # Use __slots__ to save memory, and to maintain immutability
    __slots__ = ()
    
    # Basic token properties
    def __str__(self):
        ''' Returns the text given to the token when initialized.
            May or may not be the standard DCSP name.
            
            >>> str(YES)
            'YES'
            >>> str(Token(3))
            '3'
            >>> str(Token(-3))
            '-3'
            >>> South = Token("STH", 0x4101)
            >>> South
            Token('STH', 0x4101)
            >>> str(South)
            'STH'
        '''#'''
        return self[0]
    def __int__(self):
        ''' Converts the token to an integer,
            resulting in the numerical DCSP value.
            
            >>> int(YES)
            18460
            >>> int(Token('PAR', 0x510A))
            20746
            >>> int(Token(0x1980))
            6528
            >>> int(Token(-3))
            16381
        '''#'''
        return self[1]
    text = property(fget=__str__)
    number = property(fget=__int__)
    
    # Try to be atomic
    def __iter__(self): raise AttributeError, 'Tokens are atomic.'

class Token(_tuple_Token):
    ''' Embodies a single token, with both text and integer components.
        Instances are (mostly) immutable, and may be used as dictionary keys.
        However, as keys they are not interchangable with numbers or strings.
    '''#'''
    
    # Use __slots__ to save memory, and to maintain immutability
    __slots__ = ()
    
    def __new__(klass, name, number=None, rep=None):
        ''' Returns a Token instance from its name and number,
            or either one for the DCSP tokens.
            
            >>> Token(-3)
            Token(-3)
            >>> Token('YES')
            YES
            >>> YES is Token(Token('YES'))
            True
            >>> hex(Token('T'))
            '0x4B54'
            >>> Token(')') == KET   # Beware! This is a single character token.
            False
            >>> Token(0x1481C)
            Traceback (most recent call last):
                ...
            OverflowError: int too large to convert to Token
            >>> from translation import Representation
            >>> rep=Representation({0x4101: 'Sth'}, None)
            >>> Token('Sth', rep=rep)
            Token('Sth', 0x4101)
            >>> Token(0x4101, rep=rep)
            Token('Sth', 0x4101)
        '''#'''
        if number != None:
            return _get_or_create_token(klass, str(name), int(number))
        elif rep:
            result = rep.get(name)
            if result: return result
        elif isinstance(name, (int, float, long)):
            num_type = type(name).__name__
            if isinstance(name, float): name = int(round(name))
            if -Token.opts.max_pos_int <= name < 0:
                return _get_or_create_token(klass, str(name), Token.opts.max_neg_int + name)
            elif name < -Token.opts.max_pos_int or name >= Token.opts.max_token:
                raise OverflowError, '%s too large to convert to %s' % (num_type, klass.__name__)
            else:
                return _get_or_create_token(klass, _get_token_text(name), name)
        elif isinstance(name, str):
            if rep and rep.has_key(name.upper()):
                return rep[name.upper()]
            elif _cache.has_key(name): return _cache[name]
            elif len(name) == 1:
                charnum = ord(name)
                if charnum > 0xFF:
                    raise OverflowError, '%s too large to convert to %s' % (type(name), klass.__name__)
                else:
                    return _get_or_create_token(klass, name, Token.opts.quot_prefix + charnum)
            else: raise ValueError, 'unknown token "%s"' % name
        elif isinstance(name, klass): return name
        else: raise ValueError
    
    # Components
    def category_name(self):
        ''' Returns a string representing the type of token.
            >>> YES.category_name()
            'Commands'
            >>> Token(-3).category_name()
            'Integers'
        '''#'''
        cat = self.category()
        if self.cats.has_key(cat): return self.cats[cat]
        else: return 'Unavailable'
    def category(self):
        ''' Returns the first byte of the DCSP token,
            which usually indicates its category.
            
            >>> YES.category()
            72
            >>> Token('A').category() == Token.cats['Text']
            True
        '''#'''
        return (self.number & 0xFF00) >> 8
    def value(self):
        ''' Returns a numerical value for the token.
            For integers, this is the value of the number;
            for other tokens, the second byte of the DCSP token.
            May be used as an array prefix for powers and provinces.
            
            >>> YES.value()
            28
            >>> Token('PAR', 0x510A).value()
            10
            >>> Token(0x1980).value()
            6528
            >>> Token(-3).value()
            -3
        '''#'''
        if   self.is_positive(): return self.number
        elif self.is_negative(): return self.number - self.opts.max_neg_int
        else:                    return self.number & 0x00FF
    
    # Types
    def is_text(self):
        ''' Whether the token represents an ASCII character.
            >>> YES.is_text()
            False
            >>> Token('A').is_text()
            True
        '''#'''
        return self.category() == self.cats['Text']
    def is_power(self):
        ''' Whether the token represents a power (country) of the game.
            >>> YES.is_power()
            False
            >>> UNO.is_power()
            False
            >>> Token('ENG', 0x4101).is_power()
            True
        '''#'''
        return self.category() == self.cats['Powers']
    def is_unit_type(self):
        ''' Whether the token represents a type of unit.'''
        return self.category() == self.cats['Unit_Types']
    def is_coastline(self):
        ''' Whether the token represents a specific coastline of a province.'''
        return self.category() == self.cats['Coasts']
    def is_supply(self):
        ''' Whether the token represents a province with a supply centre.
            >>> YES.is_supply()
            False
            >>> Token('FIN', 0x5425).is_supply()
            False
            >>> Token('NWY', 0x553E).is_supply()
            True
        '''#'''
        return self.is_province() and self.category() & 1 == 1
    def is_coastal(self):
        ''' Whether the token represents a coastal province;
            that is, one to or from which an army can be convoyed.
        '''#'''
        return self.category_name() in (
            'Coastal SC',
            'Coastal non-SC',
            'Bicoastal SC',
            'Bicoastal non-SC',
        )
    def is_province(self):
        ''' Whether the token represents a province.
            >>> YES.is_province()
            False
            >>> Token('FIN', 0x5425).is_province()
            True
            >>> Token('NWY', 0x553E).is_province()
            True
        '''#'''
        p_cat = self.cats['Provinces']
        return p_cat[0] <= self.category() <= p_cat[1]
    def is_integer(self):
        ''' Whether the token represents a number.
            >>> YES.is_integer()
            False
            >>> Token(3).is_integer()
            True
            >>> Token(-3).is_integer()
            True
        '''#'''
        return self.number < self.opts.max_neg_int
    def is_positive(self):
        ''' Whether the token represents a positive number.
            >>> YES.is_positive()
            False
            >>> Token(3).is_positive()
            True
            >>> Token(-3).is_positive()
            False
            >>> Token(0).is_positive()
            False
        '''#'''
        return 0 < self.number < self.opts.max_pos_int
    def is_negative(self):
        ''' Whether the token represents a negative number.
            >>> YES.is_negative()
            False
            >>> Token(3).is_negative()
            False
            >>> Token(-3).is_negative()
            True
            >>> Token(0).is_positive()
            False
        '''#'''
        return self.opts.max_pos_int <= self.number < self.opts.max_neg_int
    
    # Conversions
    def __hex__(self):
        ''' Returns a string representing this token in hexadecimal.
            By DAIDE convention, x is lower-case, hex digits are upper-case,
            and exactly four digits are displayed.
            >>> hex(YES)
            '0x481C'
        '''#'''
        return '0x%04X' % self.number
    def __repr__(self):
        ''' Returns code to reproduce the token.
            Uses the simplest form it can.
            >>> repr(Token(-3))
            'Token(-3)'
            >>> repr(YES)
            'YES'
            >>> repr(KET)
            'KET'
            >>> eval(repr(YES)) == Token('YES')
            True
            >>> repr(Token('STH', 0x4101))
            "Token('STH', 0x4101)"
        '''#'''
        from config import default_rep
        name = self.__class__.__name__
        if self.is_integer() and self.text == str(self.value()):
            return name + '(' + self.text + ')'
        elif self == KET: return 'KET'
        elif self == BRA: return 'BRA'
        elif _cache.get(self.text) == self:      return self.text
        elif default_rep.get(self.text) == self: return self.text
        elif len(self.text) == 1 and Token(self.text) == self:
            return name + '(' + repr(self.text) + ')'
        else: return name+'('+repr(self.text)+', '+('0x%04X'%self.number)+')'
    def tokenize(self): return [self]
    def key(self): return self
    key = property(fget=key)
    
    # Actions
    def __call__(self, *args):
        ''' Creates a new Message, starting with the token.
            Arguments are individually wrapped in parentheses.
            
            >>> NOT(GOF)
            Message([NOT, [GOF]])
            >>> print YES(MAP('name'))
            YES ( MAP ( "name" ) )
            >>> print IAM(Token('ENG', 0x4101), 3)
            IAM ( ENG ) ( 3 )
        '''#'''
        return Message(self, *map(_wrap, args))
    def __radd__(self, other):
        ''' Handles adding a token to a string.
            They join into one string, usually with a space between.
            Quotation marks are added as needed.
            
            >>> 'NOT' + GOF
            'NOT GOF'
            >>> 'NOT' + Token('A')
            'NOT "A"'
            >>> s = '"Hello, "' + Token('W')
            >>> s
            '"Hello, W"'
            >>> s + Token('o')
            '"Hello, Wo"'
            >>> s + YES
            '"Hello, W" YES'
        '''#'''
        if isinstance(other, (Token, Message)): other = str(other)
        elif not isinstance(other, str): return NotImplemented
        quot = self.opts.quot_char
        escape = self.opts.output_escape
        if self.is_text():
            if not other:                                       joint = quot
            elif other[-1] == quot: other = other[:-1];         joint = ''
            elif self.opts.squeeze_parens and other[-1] == '(': joint = quot
            else:                                               joint = ' ' + quot
            if self.text in (escape, quot):                     joint += escape
            return other + joint + self.text + quot
        else:
            if not other: joint = ''
            elif self.opts.squeeze_parens and (other[-1] == '(' or self == KET):
                joint = ''
            else: joint = ' '
            return other + joint + self.text


class Cache(dict, Verbose_Object):
    def __getitem__(self, key):
        result = dict.__getitem__(self, key)
        if result: self.log('Cached token', key, result)
        return result
    def get(self, key, default=None):
        result = dict.get(self, key)
        if result: self.log('Cached token', key, result)
        return result or default
    def __setitem__(self, key, value):
        self.log('Adding token', key, value)
        dict.__setitem__(self, key, value)
    def log(self, line, key, token):
        self.log_debug(17, '%s %r => Token(%r, 0x%04X)',
                line, key, token.text, token.number)
#_cache = Cache()
_cache = {}
def _get_or_create_token(klass, text, number):
    ''' Returns the token requested, using the cached item if possible.
        The cache as implemented keeps only the latest of each number;
        this could be inefficient if clients are playing in different
        variants, but that is highly unlikely.
        
        TODO: Doctests
    '''#'''
    # Fiddle with parentheses
    if text == 'BRA': text = '('
    elif text == 'KET': text = ')'
    
    key = (text, number)
    if _cache.has_key(key): item = _cache[key]
    else:
        item = super(Token, klass).__new__(klass, key)
        _cache[key] = item
    return item

def _get_token_text(number):
    ''' Finds the text for a single token number.
        >>> _get_token_text(3)
        '3'
        >>> _get_token_text(-3)
        '-3'
        >>> _get_token_text(0x2004)
        '-8188'
        >>> _get_token_text(0x4B63)
        'c'
        >>> Token.opts.ignore_unknown = True;  _get_token_text(0x581C)
        '0x581C'
        >>> Token.opts.ignore_unknown = False; _get_token_text(0x581C)
        Traceback (most recent call last):
            ...
        ValueError: unknown token number 0x581C
    '''#'''
    if   number < Token.opts.max_pos_int:             return str(number)
    elif number < Token.opts.max_neg_int:             return str(number - Token.opts.max_neg_int)
    elif (number & 0xFF00) == Token.opts.quot_prefix: return chr(number & 0x00FF)
    elif Token.opts.ignore_unknown:                   return '0x%04X' % number
    else: raise ValueError, 'unknown token number 0x%04X' % number

def _tokenize(value, wrap=False):
    ''' Returns a list of Token instances based on a value.
        If wrap is true, lists and tuples will be wrapped in parentheses.
        (But that's meant to be used only by this method.)
        
        >>> _tokenize(3)
        [Token(3)]
        >>> _tokenize('YES')
        [YES]
        >>> _tokenize('name')
        [Token('n'), Token('a'), Token('m'), Token('e')]
        >>> _tokenize([3, 0, -3])
        [Token(3), Token(0), Token(-3)]
        >>> _tokenize([3, 0, -3], True)
        [BRA, Token(3), Token(0), Token(-3), KET]
        >>> _tokenize([NOT(), (GOF,)])
        [NOT, BRA, GOF, KET]
    '''#'''
    if   isinstance(value, (int, float, long)): return [Token(value)]
    elif isinstance(value, str):
        try:                                    return [Token(value)]
        except ValueError:                      return [Token(c) for c in value]
    elif hasattr(value, 'tokenize'):
        result = value.tokenize()
        if isinstance(result, list):            return result
        else: raise TypeError, 'tokenize for %s returned non-list (type %s)' % (value, result.__class__.__name__)
    elif wrap:                                  return _wrap(value)
    else:
        try: return sum([_tokenize(item, True) for item in value], [])
        except TypeError: raise TypeError, 'Cannot tokenize ' + str(value)

def _wrap(value):
    ''' Tokenizes the list and wraps it in a pair of brackets.
        >>> _wrap(GOF)
        [BRA, GOF, KET]
        >>> _wrap(NOT(GOF))
        [BRA, NOT, BRA, GOF, KET, KET]
        >>> _wrap('name')
        [BRA, Token('n'), Token('a'), Token('m'), Token('e'), KET]
    '''#'''
    return [BRA] + _tokenize(value) + [KET]

# Testing framework
__test__ = {
    '_get_or_create_token':      _get_or_create_token,
    '_get_token_text':           _get_token_text,
    '_tokenize':                 _tokenize,
    '_wrap':                     _wrap,
}
