''' PyDip Diplomacy Message validation
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
'''#'''

__all__ = ['validate_expression', 'parse_syntax_file']

syntax = {'string': [(0, ['repeat', 'cat', 'Text'])]}

def parse_syntax_file(lines):
    ''' Parses lines from the DAIDE Message Syntax file.
        BNF-like rules are added to the syntax dictionary
        used by validate_expression().
        Returns a mapping of press levels to their names.
    '''#'''
    import re
    from language import Token
    
    tla = re.compile(r'[A-Z0-9]{3}$')
    braces = re.compile(r'{.*?}')
    strings = re.compile(r"'\w+'")
    repeats = re.compile(r'(.*) +\1 *\.\.\.')
    lev_mark = re.compile(r'<h2><a name="level(\d+)">.*: (\w[a-zA-Z ]*)<')
    bnf_rule = re.compile(r'<(?:h4|li><b)>({\w\w\w} |)(?:<a name="\w+">|)(\w+) (\+|-|)= (.*?)</(?:h4|b)>')
    syntax_level = 0
    neg_level = Token.opts.max_neg_int
    levels = []
    
    def parse_bnf(name, level, rule):
        ''' Parses a BNF-like syntax rule into dictionary form.'''
        rule = rule.replace('(', ' BRA ')
        rule = rule.replace(')', ' KET ')
        rule = rule.replace('[', ' optional ')
        rule = rule.replace(']', ' ] ')
        rule = rule.replace('...', ' ... ')
        rule = strings.sub('string', rule)
        words = parse_rule(level, rule)
        add_rule(name, level, words)
    
    def parse_rule(level, rule):
        match = repeats.search(rule)
        while match:
            rule = str.join(' ', [rule[:match.start()], 'repeat',
                    subrule(level, parse_rule(level, match.group(1))),
                    rule[match.end():]])
            match = repeats.search(rule)
        
        words = rule.split()
        while words[-1] == ']': words.pop()
        while ']' in words:
            start = None
            for index, word in enumerate(words):
                if word == ']':
                    words[start:index+1] = subrule(level,
                            words[start:index]).split()
                    break
                elif word == 'optional': start = index
        
        return words
    
    def subrule(level, words):
        ''' Returns a rule name suitable for repeat.
            May be of the form 'word', 'sub word', 'cat Word',
            'TLA', or '$auto-created-name'.
            In the last case, the new subrule will have been created.
        '''#'''
        if len(words) == 1: result = words[0]
        elif find_ket(words) == len(words) - 1:
            # Warning: Needs work for categories,
            # but the current syntax doesn't have such a situation.
            result = 'sub ' + subrule(level, words[1:-1])
        else:
            result = '$' + str.join('-', words)
            add_rule(result, level, words)
        return result
    
    def add_rule(name, level, words):
        ''' Translates token abbreviations and adds the rule.'''
        def correct(word):
            if tla.match(word): return [Token(word)]
            elif word[0].isupper() and word[1].islower(): return ['cat', word]
            else: return [word]
        rule = (level, sum([correct(word) for word in words], []))
        rules = syntax.setdefault(name, [])
        if rule not in rules: rules.append(rule)
    
    for line in lines:
        match = bnf_rule.search(line)
        if match:
            # Ignore the PDA/AOA marks, for now
            option, name, operator, rule = match.groups()
            rule = rule.replace('</a>', '')
            if operator == '+': use_level = -syntax_level
            elif operator == '-': use_level = -neg_level
            else: use_level = syntax_level
            parse_bnf(name, use_level, rule)
        else:
            match = lev_mark.search(line)
            if match:
                syntax_level = int(match.group(1))
                levels.append((syntax_level, match.group(2).strip()))
    
    return levels

#spaces = 0
def validate_expression(msg, sub, syntax_level):
    ''' Tries to match the message with the given expression level.
        Returns the number of tokens in the best match,
        and whether the full match is valid.
        Intended to be used by the Message class.
        
        >>> Eng = Token('ENG', 0x4101)
        >>> validate_expression([ORR, BRA, DRW, KET, BRA, SLO, BRA, Eng, KET, KET], 'multipart_offer', 200)
        (10, True)
        
        # Serious boundary case: Empty sub-expression valid in TRY, but nowhere else.
        >>> validate_expression(TRY([]), 'press_message', 10)
        (3, True)
        >>> validate_expression(SND(1, [], TRY([])), 'client_command', 10)
        (5, False)
        
        # Check for returning the correct error position,
        # even within nested expressions
        >>> Fra = Token('FRA', 0x4102)
        >>> m = SND(1, Eng, PRP(ORR(NOT(DRW), AND(PCE([Eng, Fra]), DRW))))
        >>> validate_expression(m, 'client_command', 40)
        (18, False)
        
        # Check for infinite recursion in HUH expressions
        >>> m = HUH([ERR, YES(NME("DumberBot", "PyDip 1.0.166"))])
        >>> validate_expression(m, 'message', 0)
        (34, True)
        
        # Check for optional unwrapped subexpressions
        >>> m = SMR([SPR, 1901], [TUR, ["Fake Player"], ["Fake_Player"], 3], [AUS, ["Fake Human Player"], ["Fake_Master"], 3])
        >>> validate_expression(m, 'message', 0)
        (71, True)
    '''#'''
    #global spaces
    if not isinstance(msg, list): raise ValueError, 'message must be a list'
    if not syntax.has_key(sub): raise ValueError, 'unknown expression "%s"' % sub
    best = 0
    valid = False
    length = len(msg)
    for level,sub_list in syntax[sub]:
        if level <= syntax_level:
            #spaces += 1
            #print ' '*spaces + 'Checking "%s" against %s' % (msg, sub_list)
            result, good = validate_option(msg, sub_list, syntax_level)
            #print ' '*spaces + 'Result: %s, %s' % (result, good)
            #spaces -= 1
            if good == valid and result > best:
                best = result
                if valid and best == length: break
            elif good and not valid:
                best = result
                valid = good
                if valid and best == length: break
    return best, valid

def validate_option(msg, item_list, syntax_level):
    ''' Tries to match the message with the given expression list.
        Returns the number of tokens in the best match,
        and whether the full match is valid.
        
        >>> validate_option([BRA, KET, BRA, YES, Token(-3)],
        ...     ['repeat', 'cat', 'Miscellaneous', YES, 'number'], 200)
        (5, True)
        >>> Eng = Token('ENG', 0x4101)
        >>> validate_option([BRA, DRW, KET, BRA, PCE, BRA, Eng, KET, KET, KET],
        ...     ['repeat', 'sub', 'offer'], 200)
        (9, True)
        >>> validate_option([BRA, DRW, KET, UNO, KET],
        ...     ['repeat', 'sub', 'offer', 'sco_power'], 200)
        (4, True)
    '''#'''
    from language import Token, BRA, KET, ERR
    from config   import token_cats
    
    index = 0
    option = None
    in_sub = in_cat = repeat = False
    length = len(msg)
    for opt in item_list:
        if isinstance(opt, str):
            if   opt == 'any':      return length, True
            elif opt == 'sub':      in_sub = True
            elif opt == 'cat':      in_cat = True
            elif opt == 'repeat':   repeat = True
            elif opt == 'optional': option = (index, True)
            else:
                if in_sub:
                    # Wrapped subexpression
                    result, good = count_subs(msg[index:], opt, repeat, syntax_level)
                    index += result
                    if not (result and good): break
                elif in_cat:
                    # Category name
                    if token_cats.has_key(opt):
                        num = token_cats[opt]
                        if isinstance(num, tuple):
                            check = lambda x: num[0] <= x.category() <= num[1]
                        else: check = lambda x: x.category() == num
                    elif opt == 'Token':
                        check = lambda x: x not in (BRA, KET, ERR)
                    else: raise ValueError, 'unknown category "%s"' % opt
                    result = count_valid(msg[index:], check, repeat)
                    if result: index += result
                    else: break
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
    return option or (index, False)

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
        Modified to accept strings as well as tokens.
        
        >>> find_ket([BRA, NOT, BRA, GOF, KET, KET, BRA, DRW, KET])
        5
        >>> find_ket([BRA, BRA, GOF, KET, BRA, DRW, KET, KET])
        7
    '''#'''
    from language import BRA, KET
    if not msg: return 0
    start = msg[0]
    if start == 'BRA': end = 'KET'
    elif start == BRA: end = KET
    else: return 0
    
    level = 1
    index = 0
    while level > 0:
        index += 1
        old_index = index
        index += msg[index:].index(end)
        level += msg[old_index:index].count(start) - 1
    return index
