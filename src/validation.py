''' PyDip Diplomacy Message validation
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
    
    Exported function: validate_expression()
        -- Determines how much of a message conforms to syntax.
    
    These functions could be optimized a bit more.
    The standard MDF message takes several CPU seconds to validate.
    The main bottleneck now appears to be count_subs(),
    followed closely by validate_option().
    I have a slightly faster version, but it fails the empty list tests.
'''#'''

__all__ = ['validate_expression']

def validate_expression(msg, sub, syntax_level):
    ''' Tries to match the message with the given expression level.
        Returns the number of tokens in the best match,
        and whether the full match is valid.
        
        >>> from language import *
        >>> Eng = Token('ENG', 0x4101)
        >>> validate_expression([ORR, BRA, DRW, KET, BRA, SLO, BRA, Eng, KET, KET], 'multipart_offer', 200)
        (10, True)
        
        # Serious boundary case: Empty sub-expression valid in TRY, but nowhere else.
        >>> validate_expression(TRY([]), 'message', 10)
        (3, True)
        >>> validate_expression(SND(1, [], TRY([])), 'client_command', 10)
        (5, False)
        
        # Check for returning the correct error position,
        # even within nested expressions
        >>> Fra = Token('FRA', 0x4102)
        >>> m = SND(1, Eng, PRP(ORR(NOT(DRW), AND(PCE([Eng, Fra]), DRW))))
        >>> validate_expression(m, 'client_command', 40)
        (18, False)
    '''#'''
    from config import syntax
    if not isinstance(msg, list): raise ValueError, 'message must be a list'
    if not syntax.has_key(sub): raise ValueError, 'unknown expression "%s"' % sub
    best = 0
    valid = False
    length = len(msg)
    for level,sub_list in syntax[sub]:
        if level == 999 or level <= syntax_level:
            result, good = validate_option(msg, sub_list, syntax_level)
            if good == valid and result > best:
                best = result
                if valid and best == length: break
            elif good and not valid:
                best = result
                valid = good
    return best, valid

def validate_option(msg, item_list, syntax_level):
    ''' Tries to match the message with the given expression list.
        Returns the number of tokens in the best match,
        and whether the full match is valid.
        
        >>> from language import *
        >>> validate_option([BRA, KET, BRA, YES, Token(-3)],
        ...     ['repeat', 'cat', 'Miscellaneous', YES, 'number'], 200)
        (5, True)
        >>> Eng = Token('ENG', 0x4101)
        >>> validate_option([BRA, DRW, KET, BRA, PCE, BRA, Eng, KET, KET, KET],
        ...     ['repeat', 'sub', 'offer'], 200)
        (9, True)
        >>> validate_option([BRA, DRW, KET, UNO, KET],
        ...     ['repeat', 'sub', 'main_offer', 'maybe_power'], 200)
        (4, True)
    '''#'''
    from language import Token
    from config   import token_cats
    
    index = 0
    in_sub = in_cat = repeat = False
    length = len(msg)
    for opt in item_list:
        if isinstance(opt, str):
            if index == length:     return index, opt == 'optional'
            elif opt == 'any':      return length, True
            elif opt == 'sub':      in_sub = True
            elif opt == 'cat':      in_cat = True
            elif opt == 'repeat':   repeat = True
            elif opt != 'optional':
                # Category name
                if in_sub:
                    result, good = count_subs(msg[index:], opt, repeat, syntax_level)
                    index += result
                    if not (result and good): break
                elif in_cat:
                    if token_cats.has_key(opt):
                        num = token_cats[opt]
                        if isinstance(num, tuple):
                            result = count_valid(msg[index:],
                                lambda x: num[0] <= x.category() <= num[1],
                                repeat)
                        else:
                            result = count_valid(msg[index:],
                                lambda x: x.category() == num, repeat)
                        if result: index += result
                        else: break
                    else: raise ValueError, 'unknown category "%s"' % opt
                else:
                    # Unwrapped subexpression(s)
                    result = validate_expression(msg[index:], opt, syntax_level)
                    index += result[0]
                    if not result[1]: break
                    if repeat:
                        while result[1]:
                            result = validate_expression(msg[index:], opt, syntax_level)
                            index += result[0]
                in_sub = in_cat = repeat = False
        elif isinstance(opt, Token):
            result = count_valid(msg[index:], lambda x: x == opt, repeat)
            repeat = False
            if result: index += result
            else: break
        else: raise UserWarning, 'Invalid State'
    else: return index, True
    return index, False

def count_valid(msg, func, repeat):
    ''' Counts the number of tokens for which the given function returns True.
        If repeat is false, only the first token will be counted.
        
        >>> count_valid([True, True, False, True], lambda x:x, False)
        1
        >>> count_valid([True, True, False, True], lambda x:x, True)
        2
        >>> count_valid([False, True, False, True], lambda x:x, True)
        0
        >>> count_valid([False, True, False, True], lambda x:x, False)
        0
    '''#'''
    if repeat:
        index = 0
        length = len(msg)
        while index < length and func(msg[index]): index += 1
        return index
    elif msg and func(msg[0]): return 1
    else: return 0

def count_subs(msg, sub, repeat, syntax_level):
    ''' Tries to match the message with the given wrapped subexpression.
        Returns a tuple: (index,valid) where index is the last matched
        expression, and valid is whether it ended on an exact boundary.
        
        >>> from language import *
        >>> Eng = Token('ENG', 0x4101)
        >>> Fra = Token('FRA', 0x4102)
        >>> msg = [
        ...     BRA, DRW, KET,
        ...     BRA, XOY, BRA, Fra, KET, BRA, Eng, KET, KET,
        ... KET ]
        ... 
        >>> count_subs(msg, 'offer', True, 40)
        (4, False)
        >>> count_subs(msg, 'offer', True, 120)
        (12, True)
    '''#'''
    from language import BRA, KET
    
    # Check for the start of a subexpression
    if not msg or msg[0] != BRA: return 0, False
    
    # Find the matching KET
    level = 1
    sublen = 0
    while level > 0:
        sublen += 1
        old_sublen = sublen
        sublen += msg[sublen:].index(KET)
        level += msg[old_sublen:sublen].count(BRA) - 1
    
    result = validate_expression(msg[1:sublen], sub, syntax_level)
    index = result[0] + 2
    if result[1]:
        if repeat:
            result, valid = count_subs(msg[index:], sub, repeat, syntax_level)
            if result: return index + result, valid
        return index, True
    else: return index - 1, False

def find_ket(msg):
    ''' Finds the index of a KET that matches the BRA starting the message.
        If the message is empty or does not start with BRA, returns 0.
        May give an error if the parentheses are imbalanced.
        
        Now obsolete, but useful to compare the algorithm above.
        
        >>> from language import *
        >>> find_ket([BRA, NOT, BRA, GOF, KET, KET, BRA, DRW, KET])
        5
        >>> find_ket([BRA, BRA, GOF, KET, BRA, DRW, KET, KET])
        7
    '''#'''
    from language import BRA, KET
    if not msg or msg[0] != BRA: return 0
    level = 1
    index = 0
    while level > 0:
        index += 1
        old_index = index
        index += msg[index:].index(KET)
        level += msg[old_index:index].count(BRA) - 1
    return index
