''' PyDip configuration management
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
    
    Harfs files for constants and other information.
    The main configuration files are pydip.cfg in the current working directory,
    and ~/.pydiprc in the user's home directory.
'''#'''

import re, os
import ConfigParser
from functions import Verbose_Object
from translation import Representation, read_message_file

# Main program version; used for bot versions
repository = '$URL$'
__version__ = repository.split('/')[-3]

# Various option classes.
class option_class(object):
    section = None
    user_config = ConfigParser.RawConfigParser()
    user_config.read(['pydip.cfg', os.path.expanduser('~/.pydiprc')])
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
        - escape_char      The character that indicates an escaped quotation mark
        - quot_char        The character in which to wrap text in Messages
        - max_token        The largest number legal for a token
        - quot_prefix      The number to add to a character's ordinal value, to get its token number
        - max_pos_int      One greater than the largest positive number representable by a token
        - max_neg_int      One greater than the token number of the most negative number representable by a token
    '''#'''
    section = 'tokens'
    def __init__(self):
        # Load values from the configuration files
        self.squeeze_parens = self.getboolean('squeeze parentheses', False)
        self.ignore_unknown = self.getboolean('ignore unknown tokens', True)
        self.input_escape   = self.getstring('input escape chararacter', '\\')[0]
        self.output_escape  = self.getstring('output escape chararacter', '\\')[0]
        self.quot_char      = self.getstring('quotation mark', '"')[0]
        
        # Calculated constants needed by the language module
        self.max_token   = (max([cat for cat in token_cats.keys()
            if isinstance(cat, int)]) + 1) << 8
        self.quot_prefix = token_cats['Text'] << 8
        self.max_pos_int = (token_cats['Integers'][1] + 1) << 7
        self.max_neg_int = self.max_pos_int << 1
class syntax_options(option_class):
    ''' Options needed by this configuration script.'''
    section = 'syntax'
    def __init__(self):
        # os.path.abspath(__file__) would be useful here.
        self.variant_file   = self.getstring('variants file',  os.path.join('docs', 'variants.html'))
        self.dcsp_file      = self.getstring('protocol file',  os.path.join('docs', 'dcsp.html'))
        self.syntax_file    = self.getstring('syntax file',    os.path.join('docs', 'dpp_syntax.html'))
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
            self.LVL = self.getint('syntax Level',                    0)
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
    def get_params(self):
        from functions import relative_limit
        from language import LVL, MTL, RTL, BTL, AOA, DSD, PDA, NPR, NPB, PTL
        params = [(LVL, self.LVL)]
        if self.MTL: params.append((MTL, relative_limit(self.MTL)))
        if self.RTL: params.append((RTL, relative_limit(self.RTL)))
        if self.BTL: params.append((BTL, relative_limit(self.BTL)))
        if self.AOA: params.append((AOA,))
        if self.DSD: params.append((DSD,))
        
        if self.LVL >= 10:
            if self.PDA: params.append((PDA,))
            if self.NPR: params.append((NPR,))
            if self.NPB: params.append((NPB,))
            if self.PTL: params.append((PTL, relative_limit(self.PTL)))
        return params
    
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
class variant_options(Verbose_Object):
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
        self.prefix      = 'variant_options(%r)' % variant_name
        self.variant     = variant_name
        self.map_name    = variant_name.lower()
        self.description = description
        self.files       = files
        self.rep         = rep or self.get_representation()
        self.seasons     = [SPR, SUM, FAL, AUT, WIN]
        self.msg_cache  = {}
    def new_judge(self):
        from judge import Standard_Judge
        return Standard_Judge(self, game_options())
    def get_representation(self):
        filename = self.files.get('rem')
        if filename: return read_representation_file(filename)
        else: return default_rep
    def read_file(self, extension):
        result = self.msg_cache.get(extension)
        if not result:
            filename = self.files.get(extension)
            if filename:
                result = read_message_file(filename, self.rep)
                self.msg_cache[extension] = result
        return result
    def cache_msg(self, extension, message):
        result = self.msg_cache.get(extension)
        if result and result != message:
            self.log_debug(7, 'Changing cached "%s" message from "%s" to "%s"',
                    extension, result, message)
        self.msg_cache[extension] = message
    def open_file(self, extension): return file(self.files[extension])
    map_mdf = property(fget = lambda self: self.read_file('mdf'),
            fset = lambda self, msg: self.cache_msg('mdf', msg))
    start_now = property(fget = lambda self: self.read_file('now'),
            fset = lambda self, msg: self.cache_msg('now', msg))
    start_sco = property(fget = lambda self: self.read_file('sco'),
            fset = lambda self, msg: self.cache_msg('sco', msg))


base_rep = None
default_rep = None
token_cats    = {}
error_strings = {}
message_types = {}
order_mask    = {}
variants      = {}
press_levels  = {}

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
        ENG
        >>> base_rep[0x481C]
        YES
        >>> message_types['Diplomacy']
        2
    '''#'''
    global base_rep
    global default_rep
    
    try: dcsp_file = open(proto_file, 'rU', 1)
    except IOError: raise IOError, "Could not find protocol file '%s'" % proto_file
    else:
        # Local variable initialization
        msg_name = None
        err_type = None
        last_cat = None
        rep_item = False
        old_line = ''
        token_names = {}
        default_tokens = {}
        
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
                    else: print 'Bad line in protocol file: ' + line
                elif line.find(' 0x') > 0:
                    match = re.search('>(\w\w\w) (0x\w\w)', line)
                    if match:
                        name = match.group(1).upper()
                        number = last_cat + int(match.group(2), 16)
                        if rep_item: default_tokens[number] = name
                        else: token_names[number] = name
            elif line.find('M)') > 0:
                match = re.match('.*The (\w+) Message', line)
                if match: msg_name = match.group(1)
            elif line.find('Version ') >= 0:
                match = re.match('.*Version (\d+)', line)
                if match: option_class.local_opts['dcsp_version'] = int(match.group(1))
            elif line.find('Magic Number =') > 0:
                option_class.local_opts['magic'] = int(re.match('.*Number = (0x\w+)', line).group(1), 16)
        dcsp_file.close()
        base_rep = Representation(token_names, None)
        default_rep = Representation(default_tokens, base_rep)
    # We may want some sanity checking here.

def read_representation_file(rep_file_name):
    ''' Parses a representation file.
        The first line contains a decimal integer, the number of tokens.
        The remaining lines consist of four hex digits, a colon,
        and the three-letter token name.
        
        >>> rep = read_representation_file('variants/sailho.rem')
        >>> rep['NTH']
        Token('NTH', 0x4100)
        
        # This used to be 'Psy'; it was probably changed for consistency.
        >>> rep[0x563B]
        Token('PSY', 0x563B)
        >>> len(rep)
        64
    '''#'''
    rep_file = open(rep_file_name, 'rU', 1)
    num_tokens = int(rep_file.readline().strip())
    if num_tokens > 0:
        rep = {}
        for line in rep_file:
            number = int(line[0:4], 16)
            name = line[5:8]
            uname = name.upper()
            if base_rep.has_key(uname):
                raise ValueError, 'Conflict with token ' + uname
            rep[number] = uname
            num_tokens -= 1
        if num_tokens == 0: return Representation(rep, base_rep)
        else: raise ValueError, 'Wrong number of lines in representation file'
    else: return default_rep

def read_syntax(syntax_file):
    ''' Opens the Message Syntax file, passing it to the validation module.'''
    from validation import parse_syntax_file
    levels = None
    
    try: syn_file = open(syntax_file, 'rU', 1)
    except IOError:
        raise IOError, "Failed to find syntax file %r" % syntax_file
    else:
        levels = parse_syntax_file(syn_file)
        syn_file.close()
    
    if levels:
        # Expand press levels to be useful to the Game class
        for i,name in levels:
            press_levels[i] = name
            press_levels[str(i)] = i
            press_levels[name.lower()] = i
    else:
        # Set reasonable press levels if the file is missing or unparsable
        for i in range(0, 200, 10) + [8000]:
            press_levels[i] = str(i)
            press_levels[str(i)] = i

def init_language():
    ''' Initializes the various tables,
        and exports the token names into the language module.
        
        >>> if not variants:
        ...     init_language()
        >>> import language
        >>> language.YES is Token('YES', 0x481C)
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
    #print 'Attempting to add tokens to language...'
    for name, token in base_rep.items():
        #print 'Adding language.%s' % (name,)
        setattr(language, name, token)
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
    import gameboard
    opts = variants['standard']
    standard_map = gameboard.Map(opts)
    extension = {
        'standard_map': standard_map,
        'standard_sco': opts.start_sco,
        'standard_now': opts.start_now,
    }
    for name,token in opts.rep.items(): extension[name] = token
    extension.update(globs)
    return extension
