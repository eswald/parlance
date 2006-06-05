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
        for item in message: list.extend(self, self.to_tokens(item))
    
    def fold(self):
        ''' Folds the token into a list, with bracketed sublists as lists.
            Also converts text and number tokens to strings and integers.
            This version takes about half the time for a map definition,
            but probably a bit longer than old_fold() for simple messages.
            
            >>> NOT(GOF).fold()
            [NOT, [GOF]]
            >>> Message().fold()
            []
            >>> NME('name')(-3).fold()
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
            
            >>> NME('version')(-3).convert()
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
            >>> print Message((NME, ["I'm Me"]), '"Missing" field "name"')
            NME ( "I'm Me" ) """Missing"" field ""name"""
            >>> str(Message('name'))
            '"name"'
        '''#'''
        from config import protocol
        opts = protocol.base_rep.opts
        quot = opts.quot_char
        escape = opts.output_escape
        squeeze = opts.squeeze_parens
        
        result = []
        in_text = False
        use_space = False
        
        for token in self:
            if token.is_text():
                if not in_text:
                    if use_space: result.append(' ')
                    else: use_space = True
                    result.append(quot)
                    in_text = True
                
                if token.text in (escape, quot): result.append(escape)
                result.append(token.text)
            else:
                if in_text:
                    result.append(quot)
                    in_text = False
                if use_space and not (squeeze and token is KET):
                    result.append(' ')
                use_space = not (squeeze and token is BRA)
                result.append(token.text)
        if in_text: result.append(quot)
        
        return str.join('', result)
    def __repr__(self):
        ''' Returns a string which can be used to reproduce the message.
            Note: Can get long, if used improperly.
            
            >>> eval(repr(NOT(GOF)))
            Message([NOT, [GOF]])
            >>> eval(repr(IAM(Token('STH', 0x4101))(42)))
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
    
    # Formerly module methods, but only used in this class.
    @staticmethod
    def to_tokens(value, wrap=False):
        ''' Returns a list of Token instances based on a value.
            If wrap is true, lists and tuples will be wrapped in parentheses.
            (But that's meant to be used only by this method.)
            
            >>> Message.to_tokens(3)
            [IntegerToken(3)]
            >>> Message.to_tokens('YES')
            [StringToken('Y'), StringToken('E'), StringToken('S')]
            >>> Message.to_tokens('name')
            [StringToken('n'), StringToken('a'), StringToken('m'), StringToken('e')]
            >>> Message.to_tokens([3, 0, -3])
            [IntegerToken(3), IntegerToken(0), IntegerToken(-3)]
            >>> Message.to_tokens([3, 0, -3], True)
            [BRA, IntegerToken(3), IntegerToken(0), IntegerToken(-3), KET]
            >>> Message.to_tokens([+NOT, (GOF,)])
            [NOT, BRA, GOF, KET]
        '''#'''
        if hasattr(value, 'tokenize'):
            result = value.tokenize()
            if isinstance(result, list): return result
            else:
                raise TypeError('tokenize for %s returned non-list (type %s)' %
                        (value, result.__class__.__name__))
        elif isinstance(value, (int, float, long)): return [IntegerToken(value)]
        elif isinstance(value, str):
            return [StringToken(c) for c in value]
        elif wrap: return Message.wrap(value)
        else:
            try: return sum([Message.to_tokens(item, True) for item in value], [])
            except TypeError: raise TypeError, 'Cannot tokenize ' + str(value)
    @staticmethod
    def wrap(value):
        ''' Tokenizes the list and wraps it in a pair of brackets.
            >>> Message.wrap(GOF)
            [BRA, GOF, KET]
            >>> Message.wrap(NOT(GOF))
            [BRA, NOT, BRA, GOF, KET, KET]
            >>> Message.wrap('name')
            [BRA, StringToken('n'), StringToken('a'), StringToken('m'), StringToken('e'), KET]
        '''#'''
        return [BRA] + Message.to_tokens(value) + [KET]
    
    # Automatically translate new items into Tokens
    def append(self, value):
        ''' Adds a new token to the Message.
            >>> m = Message(NOT)
            >>> m.append(GOF)
            >>> m
            Message([NOT, GOF])
            >>> m.append('name')
            Traceback (most recent call last):
                ...
            KeyError: "unknown token 'name'"
            >>> m.append([3])
            Traceback (most recent call last):
                ...
            TypeError: list objects are unhashable
        '''#'''
        from config import protocol
        list.append(self, protocol.base_rep[value])
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
        list.extend(self, self.to_tokens(value))
    def __add__(self, other):
        ''' Adds the given Message or list at the end of this Message,
            translating list items into Tokens if necessary.
            Note: To add a single token, use "++".
            
            >>> print ((ALY(ENG, FRA) ++ VSS) + [[GER, ITA]])
            ALY ( ENG FRA ) VSS ( GER ITA )
        '''#'''
        return Message(list.__add__(self, other))
    def __iadd__(self, other): self.extend(other); return self
    
    def __call__(self, *args):
        ''' Makes the standard bracketing patterns legal Python.
            Unfortunately, multiple values in a single bracket need commas.
            
            >>> print NME ('name') ('version')
            NME ( "name" ) ( "version" )
            >>> print CCD (ENG) (SPR, 1901)
            CCD ( ENG ) ( SPR 1901 )
        '''#'''
        if len(args) == 1: return self + self.wrap(*args)
        else: return self + self.wrap(args)
    __and__ = __call__
    def __iand__(self, other):
        try:
            if len(other) == 1: other = other[0]
        except TypeError: pass
        list.extend(self, self.wrap(other)); return self
    def __mod__(self, other):
        ''' Wraps each element of a list individually,
            appending them to a copy of the message.
            
            >>> units = standard_now.fold()[5:8]
            >>> print NOW (FAL, 1901) % units
            NOW ( FAL 1901 ) ( ENG FLT LON ) ( ENG FLT EDI ) ( ENG AMY LVP )
        '''#'''
        return reduce(apply, [(item,) for item in other], self)
    
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
        try: list.__setslice__(self, from_index, to_index, self.to_tokens(value))
        except TypeError: raise TypeError, 'must assign list (not "%s") to slice' % type(value).__name__
    def __setitem__(self, index, value):
        ''' Replaces a single Token of the Message with another Token.
            >>> m = NOT(GOF)
            >>> m[2] = DRW; print m
            NOT ( DRW )
            >>> m[-1] = 42; print m
            NOT ( DRW 42
            >>> m[3]
            IntegerToken(42)
            >>> m[-2] = [YES, KET]
            Traceback (most recent call last):
                ...
            TypeError: list objects are unhashable
        '''#'''
        from config import protocol
        list.__setitem__(self, index, protocol.base_rep[value])
    def insert(self, index, value):
        ''' Inserts a single token into the Message.
            >>> m = HUH(WHT)
            >>> m.insert(2, ERR)
            >>> str(m)
            'HUH ( ERR WHT )'
            >>> m.insert(3, [Token('ENG', 0x4101), Token('FRA', 0x4102)])
            Traceback (most recent call last):
                ...
            TypeError: list objects are unhashable
        '''#'''
        from config import protocol
        list.insert(self, index, protocol.base_rep[value])


class _integer_Token(int):
    ''' Core for the Token class, based on an integer.
        Advantages over the tuple-based class:
            - Doesn't confuse string interpolation
            - Slightly faster
        Possible disadvantages:
            - Easier to use improperly in arithmetic
            - Compares equal to integers and tokens with different names
            - Sorts by number, not text; particularly relevant for provinces
            - Token 0x0000 is a false value
    '''#'''
    
    # Use __slots__ to save memory, and to maintain immutability
    __slots__ = ('text')
    
    def __new__(klass, key):
        ''' Converts the token to an integer,
            resulting in the numerical DCSP value.
            
            # Moved here from the old __int__() method
            >>> int(YES)
            18460
            >>> int(Token('PAR', 0x510A))
            20746
            >>> int(IntegerToken(0x1980))
            6528
            >>> int(IntegerToken(-3))
            16381
        '''#'''
        name, number = key
        result = super(_integer_Token, klass).__new__(klass, number)
        result.text = name
        return result
    
    # Basic token properties
    def __str__(self):
        ''' Returns the text given to the token when initialized.
            May or may not be the standard DCSP name.
            
            >>> str(YES)
            'YES'
            >>> str(IntegerToken(3))
            '3'
            >>> str(IntegerToken(-3))
            '-3'
            >>> South = Token("STH", 0x4101)
            >>> South
            Token('STH', 0x4101)
            >>> str(South)
            'STH'
        '''#'''
        return self.text
    number = property(fget=int)
    
    # Avoid changing the text
    def __setattr__(self, name, value):
        if hasattr(self, name):
            raise AttributeError("'%s' object attribute '%s' is read-only" %
                    self.__class__.__name__, name)
        else: super(_integer_Token, self).__setattr__(name, value)

class Token(_integer_Token):
    ''' Embodies a single token, with both text and integer components.
        Instances are (mostly) immutable, and may be used as dictionary keys.
        However, as keys they are not interchangable with numbers or strings.
    '''#'''
    
    # Use __slots__ to save memory, and to maintain immutability
    __slots__ = ('category')
    cache = {}
    
    def __new__(klass, name, number):
        ''' Returns a Token instance from its name and number.
            If you only have one, use "config.protocol.base_rep[key]".
            
            # Moved here from the old category() method
            >>> YES.category
            72
            >>> StringToken('A').category == Token.cats['Text']
            True
        '''#'''
        # Fiddle with parentheses
        if name == 'BRA': name = '('
        elif name == 'KET': name = ')'
        
        key = (name, number)
        result = Token.cache.get(key)
        if result is None:
            result = super(Token, klass).__new__(klass, key)
            result.category = (number & 0xFF00) >> 8
            Token.cache[key] = result
        return result
    
    # Components
    def category_name(self):
        ''' Returns a string representing the type of token.
            >>> YES.category_name()
            'Commands'
            >>> IntegerToken(-3).category_name()
            'Integers'
        '''#'''
        cat = self.category
        if self.cats.has_key(cat): return self.cats[cat]
        else: return 'Unavailable'
    def value(self):
        ''' Returns a numerical value for the token.
            For integers, this is the value of the number;
            for other tokens, the second byte of the DCSP token.
            May be used as an array prefix for powers and provinces.
            
            >>> YES.value()
            28
            >>> Token('PAR', 0x510A).value()
            10
            >>> IntegerToken(0x1980).value()
            6528
            >>> IntegerToken(-3).value()
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
            >>> StringToken('A').is_text()
            True
        '''#'''
        return self.category == self.cats['Text']
    def is_power(self):
        ''' Whether the token represents a power (country) of the game.
            >>> YES.is_power()
            False
            >>> UNO.is_power()
            False
            >>> Token('ENG', 0x4101).is_power()
            True
        '''#'''
        return self.category == self.cats['Powers']
    def is_unit_type(self):
        ''' Whether the token represents a type of unit.'''
        return self.category == self.cats['Unit_Types']
    def is_coastline(self):
        ''' Whether the token represents a specific coastline of a province.'''
        return self.category == self.cats['Coasts']
    def is_supply(self):
        ''' Whether the token represents a province with a supply centre.
            >>> YES.is_supply()
            False
            >>> Token('FIN', 0x5425).is_supply()
            False
            >>> Token('NWY', 0x553E).is_supply()
            True
        '''#'''
        return self.is_province() and self.category & 1 == 1
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
        return p_cat[0] <= self.category <= p_cat[1]
    def is_integer(self):
        ''' Whether the token represents a number.
            >>> YES.is_integer()
            False
            >>> IntegerToken(3).is_integer()
            True
            >>> IntegerToken(-3).is_integer()
            True
        '''#'''
        return self.number < self.opts.max_neg_int
    def is_positive(self):
        ''' Whether the token represents a positive number.
            >>> YES.is_positive()
            False
            >>> IntegerToken(3).is_positive()
            True
            >>> IntegerToken(-3).is_positive()
            False
            >>> IntegerToken(0).is_positive()
            False
        '''#'''
        return 0 < self.number < self.opts.max_pos_int
    def is_negative(self):
        ''' Whether the token represents a negative number.
            >>> YES.is_negative()
            False
            >>> IntegerToken(3).is_negative()
            False
            >>> IntegerToken(-3).is_negative()
            True
            >>> IntegerToken(0).is_positive()
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
            >>> repr(IntegerToken(-3))
            'IntegerToken(-3)'
            >>> repr(YES)
            'YES'
            >>> repr(KET)
            'KET'
            >>> eval(repr(YES)) == base_rep['YES']
            True
            >>> repr(Token('STH', 0x4101))
            "Token('STH', 0x4101)"
        '''#'''
        from config import protocol
        name = self.__class__.__name__
        if self.is_integer() and self.text == str(self.value()):
            return name + '(' + self.text + ')'
        elif self == KET: return 'KET'
        elif self == BRA: return 'BRA'
        elif protocol.default_rep.get(self.text) == self: return self.text
        elif len(self.text) == 1 and StringToken(self.text) == self:
            return name + '(' + repr(self.text) + ')'
        else: return name+'('+repr(self.text)+', '+('0x%04X'%self.number)+')'
    def tokenize(self): return [self]
    def key(self): return self
    key = property(fget=key)
    
    # Actions
    def __call__(self, *args):
        ''' Creates a new Message, starting with the token.
            The arguments are wrapped in brackets;
            call the result to add more parameters.
            
            >>> print NOT(GOF)
            NOT ( GOF )
            >>> print YES(MAP('name'))
            YES ( MAP ( "name" ) )
            >>> print DRW (ENG, FRA, GER)
            DRW ( ENG FRA GER )
            >>> print TRY()
            TRY ( )
            >>> print NOW (standard_map.current_turn)
            NOW ( SPR 1901 )
        '''#'''
        return Message(self)(*args)
    def __add__(self, other):
        ''' A token can be added to the front of a message.
            >>> press = PRP(PCE(ENG, FRA))
            >>> print HUH(ERR + press)
            HUH ( ERR PRP ( PCE ( ENG FRA ) ) )
        '''#'''
        return Message(self) + Message(other)
    def __pos__(self):
        ''' Creates a Message containing only this token.
            >>> +OBS
            Message([OBS])
            >>> print HUH(DRW(ENG) ++ ERR)
            HUH ( DRW ( ENG ) ERR )
        '''#'''
        return Message(self)
    
    # Shortcuts for treating Tokens as Messages
    def __and__(self, other): return Message(self) & other
    def __mod__(self, other): return Message(self) % other

class StringToken(Token):
    ''' A token of a DM string, encoding a single ASCII character.
        (Or, perhaps, a UTF-8 byte.)
    '''#'''
    
    # Use __slots__ to save memory, and to maintain immutability
    __slots__ = ()
    cache = {}
    
    def __new__(klass, char):
        result = StringToken.cache.get(char)
        if result is None:
            charnum = ord(char)
            if charnum > 0xFF:
                raise OverflowError, '%s too large to convert to %s' % (type(char), klass.__name__)
            else:
                result = Token.__new__(klass, char, Token.opts.quot_prefix + charnum)
            StringToken.cache[char] = result
        return result

class IntegerToken(Token):
    ''' A token representing a DM integer.
        Only supports 14-bit two's-complement numbers.
    '''#'''
    
    # Use __slots__ to save memory, and to maintain immutability
    __slots__ = ()
    cache = {}
    
    def __new__(klass, number):
        pos = Token.opts.max_pos_int
        neg = Token.opts.max_neg_int
        number = int(number)
        if number < 0: key = number + neg
        else: key = number
        result = IntegerToken.cache.get(key)
        if result is None:
            if number < -pos:
                raise OverflowError, '%s too large to convert to %s' % (
                        type(number).__name__, klass.__name__)
            elif number < pos:
                name = str(number)
            elif number < neg:
                name = str(number - neg)
            else:
                raise OverflowError, '%s too large to convert to %s' % (
                        type(number).__name__, klass.__name__)
            result = Token.__new__(klass, name, key)
            IntegerToken.cache[key] = result
        return result
