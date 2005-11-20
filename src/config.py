''' DAIDE Configuration Manager
    Harfs files for constants and other information.
    The main configuration files are pydip.cfg in the current working directory,
    and ~/.pydiprc in the user's home directory.
'''#'''

import re, os
import ConfigParser

# Various option classes.
class option_class(object):
    section = None
    user_config = ConfigParser.RawConfigParser()
    user_config.read(['PyDip.cfg', os.path.expanduser('~/.pydiprc')])
    local_opts = {}
    def update(self, option_dict):
        for key in option_dict:
            if hasattr(self, key):
                setattr(self, key, option_dict[key])
    
    def setboolean(self, varname, option, default):
        setattr(self, varname, self.local_opts.get(varname,
            self.getboolean(option, default)))
    def getboolean(self, option, default):
        if self.local_opts.has_key(option): return self.local_opts[option]
        if self.user_config.has_option(self.section, option):
            try: return self.user_config.getboolean(self.section, option)
            except ValueError:
                print 'Warning: Unrecognized boolean value for %s, in section %s of the configuration file.  Try "yes" or "no".' % (option, self.section)
                return default
        else: return default
    def getfloat(self, option, default):
        if self.local_opts.has_key(option): return self.local_opts[option]
        if self.user_config.has_option(self.section, option):
            try: return float(self.getstring(option, default))
            except ValueError:
                print 'Warning: Unrecognized numeric value for %s, in section %s of the configuration file.' % (option, self.section)
                return default
        else: return default
    def getint(self, option, default):
        if self.local_opts.has_key(option): return self.local_opts[option]
        if self.user_config.has_option(self.section, option):
            try: return self.user_config.getint(self.section, option)
            except ValueError:
                try: return int(self.getstring(option, default), 16)
                except ValueError:
                    print 'Warning: Unrecognized integer value for %s, in section %s of the configuration file.' % (option, self.section)
                    return default
        else: return default
    def getstring(self, option, default):
        if self.local_opts.has_key(option): return self.local_opts[option]
        if self.user_config.has_option(self.section, option):
            return self.user_config.get(self.section, option)
        else: return default
    def getlist(self, option, default):
        if self.local_opts.has_key(option): return self.local_opts[option]
        text = self.getstring(option, default)
        return [r for r in [s.strip() for s in text.split(',')] if r]
class token_options(option_class):
    ''' Options for token and message handling.
        - squeeze_parens   Whether to print spaces on the inside of parentheses
        - ignore_unknown   Whether to send error messages on receipt of unknown tokens in Diplomacy Messages
        - double_quotes    Whether to use doubled or escaped quotation marks to note quotation marks in text
        - escape_char      The character that indicates an escaped quotation mark
        - quot_char        The character in which to wrap text in Messages
        - max_token        The largest number legal for a token
        - quot_prefix      The number to add to a character's ordinal value, to get its token number
        - quot_number      The token number of the quotation mark character
        - max_pos_int      One greater than the largest positive number representable by a token
        - max_neg_int      One greater than the token number of the most negative number representable by a token
    '''#'''
    section = 'tokens'
    def __init__(self):
        # Load values from the configuration files
        self.squeeze_parens = self.getboolean('squeeze parens', False)
        self.ignore_unknown = self.getboolean('ignore unknown', False)
        self.double_quotes  = self.getboolean('double quotes',  True)
        self.escape_char    = self.getstring('escape char',    '\\')
        self.quot_char      = self.getstring('quot char',      '"')
        
        # Calculated constants needed by the language module
        self.max_token   = (max([cat for cat in token_cats.keys()
            if isinstance(cat, int)]) + 1) << 8
        self.quot_prefix = token_cats['Text'] << 8
        self.quot_number = self.quot_prefix | ord(self.quot_char)
        self.max_pos_int = (token_cats['Integers'][1] + 1) << 7
        self.max_neg_int = self.max_pos_int << 1
class syntax_options(option_class):
    ''' Options needed by this configuration script.
    '''#'''
    section = 'syntax'
    def __init__(self):
        self.variant_file   = self.getstring('variants file',  os.path.join('docs', 'variants.html'))
        self.dcsp_file      = self.getstring('protocol file',  os.path.join('docs', 'dcsp.html'))
        self.syntax_file    = self.getstring('syntax file',    os.path.join('docs', 'syntax.txt'))
        self.move_phases    = self.getlist('move phases',      'SPR,FAL')
        self.retreat_phases = self.getlist('retreat phases',   'SUM,AUT')
        self.build_phases   = self.getlist('build phases',     'WIN')
        self.move_phase     = self.getint('move order mask',    0x20)
        self.retreat_phase  = self.getint('retreat order mask', 0x40)
        self.build_phase    = self.getint('build order mask',   0x80)
class game_options(option_class):
    "Options sent in the HLO message."
    BTL = RTL = MTL = PTL = TRN = 0
    PDA = AOA = NPB = NPR = DSD = False
    section = 'game'
    
    def __init__(self, message=None):
        ''' Creates a new instance from a HLO message,
            from a dictionary, or from the configuration files.
        '''#'''
        from language import Message
        if isinstance(message, Message):
            for var_opt in message.fold()[3]:
                if   len(var_opt) == 1: setattr(self, var_opt[0].text, True)
                elif len(var_opt) == 2: setattr(self, var_opt[0].text, var_opt[1])
                else: raise ValueError, 'invalid HLO message'
        else:
            # Initialize from configuration files
            self.LVL = self.getint('syntax Level',                    200)
            self.BTL = self.getint('Build Time Limit',                0)
            self.RTL = self.getint('Retreat Time Limit',              0)
            self.MTL = self.getint('Move Time Limit',                 0)
            self.PTL = self.getint('Press Time Limit',                0)
            self.setboolean('PDA', 'Partial Draws Allowed',           False)
            self.setboolean('AOA', 'Any Orders Allowed',              False)
            self.setboolean('NPB', 'No Press during Builds',          False)
            self.setboolean('NPR', 'No Press during Retreats',        False)
            self.setboolean('DSD', 'Deadline Stops on Disconnection', False)
            self.setboolean('TRN', 'Tournament',                      False)
            
            # Sanity checks
            if self.LVL >= 10:
                if self.MTL > 0:
                    if self.PTL >= self.MTL: self.PTL = self.MTL
                else: self.PTL = 0
            else:
                self.PTL = 0
                self.PDA = False
    
    # Idea for future expansion:
    # Press Types (SND?)
        # Bit vector in integer field:
            #  0  Can send signed partial press
            #  1  Can send anonymous partial press
            #  2  Can fake sender in partial press
            #  3  Can fake recipients in partial press
            #  4  Can fake partial press as broadcast
            #  5  Can send signed broadcast press
            #  6  Can send anonymous broadcast press
            #  7  Can fake sender in broadcast press
            #  8  Can fake recipients in broadcast press
            #  9  Can fake broadcast press as partial
            # 10  Touching powers can send press
            # 11  Non-touching powers can send press
            # 12  Non-map players can send press
            # 13  Observers can send press
        # White:    3073 Your own identity given, can't be faked. (Default)
        # Black:    3077 You choose the identity to give
        # Grey:     3074 Anonymous
        # Public:   3104 Broadcast only
        # Yellow:   3136 Anonymous broadcast
        # Fake:     3081 Faked set of recipients
        # Touch:    1025 Only between powers with touching units
        # Backseat: 4128 Only non-map powers, and them broadcast-only
    # Tournaments (TRN)
class variant_options:
    ''' Options set by the game variant.
        - map_name     The name to send in MAP messages
        - map_mdf      The map definition message
        - rep          The representation dictionary
        - start_sco    The initial supply center ownerships
        - start_now    The initial unit positions
        - seasons      The list of seasons in a year
    '''#'''
    def __init__(self, variant_name, description, files, rep=None):
        ''' Finds and loads the variant files.
            This implementation requires rem, mdf, sco, and now files,
            as distributed by David Norman's server.
            Throws exceptions if something is wrong.
        '''#'''
        from language import SPR, SUM, FAL, AUT, WIN
        self.variant     = variant_name
        self.map_name    = variant_name.lower()
        self.description = description
        self.files       = files
        self.rep         = rep or self.get_representation()
        self.start_sco   = self.read_file('sco')
        self.start_now   = self.read_file('now')
        self.seasons     = [SPR, SUM, FAL, AUT, WIN]
        self.__mdf       = None
    def new_judge(self):
        from gameboard import Map
        from judge import Standard_Judge
        return Standard_Judge(self, game_options())
    def get_representation(self):
        filename = self.files.get('rem')
        if filename: return read_representation_file(filename)
        else: return default_rep
    def read_file(self, extension):
        from translation import read_message_file
        filename = self.files.get(extension.lower())
        if filename: return read_message_file(filename, self.rep)
        else: return None
    def open_file(self, extension):
        return file(self.files[extension.lower()])
    def get_mdf(self):
        if not self.__mdf: self.__mdf = self.read_file('mdf')
        return self.__mdf
    def set_mdf(self, message): self.__mdf = message
    map_mdf = property(fget=get_mdf, fset=set_mdf)


syntax        = {}
token_cats    = {}
error_strings = {}
default_rep   = {}
token_names   = {}
message_types = {}
order_mask    = {}
variants      = {}

# File parsing
def parse_variants(variant_file):
    try: var_file = open(variant_file, 'rU', 1)
    except IOError: raise IOError, "Could not find variants file '%s'" % variant_file
    else:
        name_pattern = re.compile('<td>(\w[^<]*)</td><td>(\w+)</td>')
        file_pattern = re.compile("<a href='([^']+)'>(\w+)</a>")
        for line in var_file:
            match = name_pattern.search(line)
            if match:
                descrip, name = match.groups()
                files = {}
                while match:
                    match = file_pattern.search(line, match.end())
                    if match:
                        ref, ext = match.groups()
                        files[ext.lower()] = os.path.normpath(os.path.join(
                            os.path.dirname(variant_file), ref))
                variants[name] = variant_options(name, descrip, files)

def parse_dcsp(proto_file):
    ''' Pulls token values and other constants from Andrew Rose's
        Client-Server Protocol file.
        Rather dependent on precise formatting,
        but benefits greatly from trimming Microslop junk.
        
        >>> parse_dcsp('docs/dcsp.html')
        >>> token_cats[0x42]
        'Unit Types'
        >>> token_cats['Unit_Types']
        66
        >>> error_strings[5]
        'Version incompatibility'
        >>> default_rep[0x4101]
        'ENG'
        >>> token_names[0x481C]
        'YES'
        >>> message_types['Diplomacy']
        2
    '''#'''
    try: dcsp_file = open(proto_file, 'rU', 1)
    except IOError: raise IOError, "Could not find protocol file '%s'" % proto_file
    else:
        # Local variable initialization
        msg_name = None
        err_type = None
        last_cat = None
        rep_item = False
        old_line = ''
        
        for line in dcsp_file:
            if old_line: line = old_line + ' ' + line.strip()
            pos = line.find('>0x')
            if pos > 0:
                # Given sepearately, because the error description
                # might be on the same line as the type number.
                pos2 = pos + line[pos:].find('<')
                err_type = int(line[pos+1:pos2], 16)
            
            if err_type:
                match = re.match('.*>(\w+ [\w ]+)<', line)
                if match:
                    error_strings[err_type] = match.group(1)
                    err_type = None
                    old_line = ''
                else: old_line = line[line.rfind('>'):].strip()
            elif msg_name:
                if line.find('Message Type =') > 0:
                    type_num = int(re.match('.*Type = (\d+)', line).group(1))
                    message_types[msg_name] = type_num
                    msg_name = ''
            elif line.find(' (0x') > 0:
                match = re.match('.*?[> ](\w[\w ]+) \((0x\w\w)', line)
                descrip = match.group(1)
                start_cat = int(match.group(2), 16)
                match = re.match('.* (0x\w\w)\)', line)
                if match:
                    last_cat = int(match.group(1), 16)
                    token_cats[descrip.replace(' ', '_')] = (start_cat, last_cat)
                    for i in range(start_cat, last_cat + 1):
                        token_cats[i] = descrip
                else:
                    rep_item = descrip == 'Powers'
                    last_cat = start_cat << 8
                    token_cats[descrip.replace(' ', '_')] = start_cat
                    token_cats[start_cat] = descrip
            elif last_cat:
                if line.find('category =') > 0:
                    # This must come before the ' 0x' search.
                    match = re.match('.*>([\w -]+) category = (0x\w\w)<', line)
                    if match:
                        last_cat = int(match.group(2), 16)
                        token_cats[last_cat] = descrip = match.group(1)
                        token_cats[descrip.replace(' ', '_')] = last_cat
                        rep_item = True
                        last_cat <<= 8
                    else: print 'Bad line: ' + line
                elif line.find(' 0x') > 0:
                    match = re.match('.*(\w\w\w) (0x\w\w)', line)
                    name = match.group(1).upper()
                    number = last_cat + int(match.group(2), 16)
                    if rep_item: default_rep[number] = name; default_rep[name] = number
                    else:        token_names[number] = name
            elif line.find('M)') > 0:
                match = re.match('.*The (\w+) Message', line)
                if match: msg_name = match.group(1)
            elif line.find('Version ') >= 0:
                match = re.match('.*Version (\d+)', line)
                if match: option_class.local_opts['dcsp_version'] = int(match.group(1))
            elif line.find('Magic Number =') > 0:
                option_class.local_opts['magic'] = int(re.match('.*Number = (0x\w+)', line).group(1), 16)
        dcsp_file.close()
    # We may want some sanity checking here.

def read_representation_file(rep_file_name):
    ''' Parses a representation file.
        The first line contains a decimal integer, the number of tokens.
        The remaining lines consist of four hex digits, a colon,
        and the three-letter token name.
        
        >>> rep = read_representation_file('variants/sailho.rem')
        >>> rep['NTH']
        16640
        >>> rep[0x563B]
        'Psy'
        >>> len(rep)
        128
    '''#'''
    from language import _cache
    rep_file = open(rep_file_name, 'rU', 1)
    num_tokens = int(rep_file.readline().strip())
    if num_tokens > 0:
        rep = {}
        for line in rep_file:
            number = int(line[0:4], 16)
            name = line[5:8]
            uname = name.upper()
            if _cache.has_key(uname):
                raise ValueError, 'Conflict with token ' + uname
            rep[number] = uname
            rep[uname] = number
            num_tokens -= 1
        if num_tokens == 0: return rep
        else: raise ValueError, 'Wrong number of lines in representation file'
    else: return default_rep

def read_syntax(syntax_file):
    ''' Reads the DPP language file, filling the syntax global dictionary.
        syntax will have expression names as keys; values in the form
            [(level, [item, ...]), ...]
        
        >>> if not syntax: read_syntax('docs/syntax.txt')
        ... 
        >>> syntax['thought']
        [(60, [THK, 'sub', 'main_offer']), (60, [FCT, 'sub', 'main_offer'])]
        >>> syntax['unit_adjacency']
        [(-1, [AMY]), (-1, ['cat', 'Unit_Types', 'repeat', 'province_maybe_coast']), (-1, ['sub', 'unit_coast', 'repeat', 'province_maybe_coast'])]
    '''#'''
    from language import Token
    try: syn_file = open(syntax_file, 'rU', 1)
    except IOError: raise IOError, "Could not find protocol file '%s'" % syntax_file
    else:
        for line in syn_file:
            comment = line.find(';')
            if comment >= 0: words = line[:comment].split()
            else: words = line.split()
            if words:
                sub = words.pop(0)
                if sub[0] == '{': continue # Ignore variables, for now
                level = int(words.pop(0))
                option = []
                append = option.append
                bracketed = False
                for item in words:
                    if item[0] == '[':
                        if item[-1] == ']':
                            append(item[1:-1])
                        else:
                            append(item[1:])
                            bracketed = True
                    elif bracketed:
                        if item[-1] == ']':
                            if len(item) > 1: append(item[:-1])
                            bracketed = False
                        else: append(item)
                    else: append(Token(item))
                syntax.setdefault(sub,[]).append((level,option))
        syn_file.close()

def init_language():
    ''' Initializes the various tables,
        and exports the token names into the language module.
        
        >>> if not syntax: init_language()
        ... 
        >>> import language
        >>> language.YES is language._cache['YES']
        1
        >>> language.Token.opts.quot_number == language.Token(Token.opts.quot_char).number
        1
        >>> language.KET.text
        ')'
    '''#'''
    opts = syntax_options()
    parse_dcsp(opts.dcsp_file)
    
    # Masks to determine whether an order is valid during a given phase
    order_mask[None] = opts.move_phase + opts.retreat_phase + opts.build_phase
    
    # Export variables into the language globals
    import language
    language.Token.cats = token_cats
    language.Token.opts = token_options()
    for number, name in token_names.iteritems():
        token = language.Token(name, number)
        setattr(language, name, token)
        language._cache[name.upper()] = token
        if   name in opts.move_phases:    order_mask[token] = opts.move_phase
        elif name in opts.retreat_phases: order_mask[token] = opts.retreat_phase
        elif name in opts.build_phases:   order_mask[token] = opts.build_phase
    
    parse_variants(opts.variant_file)
    read_syntax(opts.syntax_file)
init_language()


def extend_globals(globs):
    ''' Inserts into the given dictionary elements required by certain doctests.
        Namely,
        - standard_map
        - standard_sco
        - standard_now
        - The default map tokens (ENG, NWY, etc.)
        
        This takes several seconds, so only do it if necessary.
    '''#'''
    import gameboard, language
    opts = variants['standard']
    standard_map = gameboard.Map(options=opts)
    extension = {
        'standard_map': standard_map,
        'standard_sco': opts.start_sco,
        'standard_now': opts.start_now,
    }
    for key,value in default_rep.iteritems():
        if isinstance(value, int): extension[key] = language.Token(key, value)
    extension.update(globs)
    return extension


def _test():
    import doctest, config
    return doctest.testmod(config)
if __name__ == "__main__": _test()

# vim: sts=4 sw=4 et tw=75 fo=crql1
