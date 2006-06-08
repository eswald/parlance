''' PyDip configuration management
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
    
    Harfs files for constants and other information.
    The main configuration files are pydip.cfg in the current working directory,
    and ~/.pydiprc in the user's home directory.
'''#'''

import re, os
import weakref
import ConfigParser
from functions import autosuper, settable_property
from translation import Representation, read_message_file

# Main program version; used for bot versions
repository = '$URL$'
__version__ = repository.split('/')[-3]

# Various option classes.
class Configuration(object):
    ''' Container for various configurable settings and constants.
        Each subclass may have an __options__ member, treated somewhat like
        __slots__ in that it builds on, rather than supplants, those in parent
        classes.  The __options__ member should be a sequence of tuples:
        (name, type, default, alternate name(s), help line, ...)
        
        For each item of __options__, all instances of the class will have
        a member by that name, set either from the command line, the main
        configuration files, the default value, or elsewhere in the program.
        Each instance may be modified independently, but set_globally()
        can be used to set all of them at once.
        
        The subclass may also have a __section__ member, indicating the
        section of the configuration file under which its corresponding
        options should be located.  If it does not have one, the name of
        the class's module will be used.
    '''#'''
    __metaclass__ = autosuper
    _user_config = ConfigParser.RawConfigParser()
    _user_config.read(['pydip.cfg', os.path.expanduser('~/.pydiprc')])
    _local_opts = {}
    _configurations = weakref.WeakValueDictionary()
    
    def __init__(self):
        self.parse_options(self.__class__)
        self._configurations[id(self)] = self
    def parse_options(self, klass):
        for cls in reversed(klass.__mro__):
            section = getattr(cls, '__section__', cls.__module__)
            opts = getattr(cls, '__options__', ())
            for item in opts: self.add_option(section, *item)
    def add_option(self, section, name, option_type, default, alt_names, *help):
        value = default
        if self._local_opts.has_key(name):
            value = self._local_opts[name]
        else:
            get = self.__getters.get(option_type, option_type)
            conf_val = get(self, name, section)
            if conf_val is not None: value = conf_val
            elif isinstance(alt_names, str):
                if len(alt_names) > 1:
                    val = get(self, name, section)
                    if val is not None: value = val
            elif alt_names:
                for item in alt_names:
                    if len(item) > 1:
                        val = get(self, name, section)
                        if val is not None:
                            value = val
                            break
            self._local_opts[name] = value
        setattr(self, name, value)
    
    @classmethod
    def set_globally(klass, name, value):
        klass._local_opts[name] = value
        for conf in klass._configurations.values():
            if hasattr(conf, name): setattr(conf, name, value)
    def update(self, option_dict):
        for key in option_dict:
            if hasattr(self, key):
                setattr(self, key, option_dict[key])
    def warn(self, line, option, section, suggestion=None):
        line = 'Warning: %s for %s, in section %s of the configuration file.'
        if suggestion: line += '  ' % suggestion
        print line % (line, option, section)
    
    # Getters for standard item types
    def getboolean(self, option, section):
        if self._user_config.has_option(section, option):
            try: result = self._user_config.getboolean(section, option)
            except ValueError:
                self.warn('Unrecognized boolean value', option, section,
                        'Try "yes" or "no".')
                result = None
        else: result = None
        return result
    def getfloat(self, option, section):
        if self._user_config.has_option(section, option):
            try: result = float(self.getstring(option, section))
            except ValueError:
                self.warn('Unrecognized numeric value', option, section)
                result = None
        else: result = None
        return result
    def getint(self, option, section):
        if self._user_config.has_option(section, option):
            try: result = self._user_config.getint(section, option)
            except ValueError:
                try: result = int(self.getstring(option, section), 16)
                except ValueError:
                    self.warn('Unrecognized integer value', option, section)
                    result = None
        else: result = None
        return result
    def getstring(self, option, section):
        if self._user_config.has_option(section, option):
            result = self._user_config.get(section, option)
        else: result = None
        return result
    def getlist(self, option, section):
        text = self.getstring(option, section)
        if text is None: result = None
        else: result = [r for r in [s.strip() for s in text.split(',')] if r]
        return result
    
    __getters = {
        bool: getboolean,
        float: getfloat,
        int: getint,
        str: getstring,
        file: getstring,  # Todo: Write something to verify this
        list: getlist,
    }

class TokenOptions(Configuration):
    ''' Options for token and message handling.
        This class will also be outfitted with the following:
        - max_token        The largest number legal for a token
        - quot_prefix      The number to add to a character's ordinal value, to get its token number
        - max_pos_int      One greater than the largest positive number representable by a token
        - max_neg_int      One greater than the token number of the most negative number representable by a token
    '''#'''
    def character(self, option, section):
        text = self.getstring(option, section)
        if not text: result = None
        elif len(text) > 1:
            self.warn('Only one character expected', option, section)
            result = text[0]
        else: result = text
        return result
    
    __section__ = 'tokens'
    __options__ = (
        ('squeeze_parens', bool, False, 'squeeze parentheses',
            'Whether to omit the spaces just inside parentheses when printing messages.'),
        ('ignore_unknown', bool, True, 'ignore unknown tokens',
            'Whether to allow tokens not represented in the protocol document or RM.',
            'If this is false, unknown tokens in a DM will result in an Error Message.'),
        ('input_escape', character, '\\', 'input escape chararacter',
            'The character which escapes quotation marks when translating messages.',
            'This can be the same as the quotation mark character itself.'),
        ('output_escape', character, '\\', 'output escape chararacter',
            'The character with which to escape quotation marks when printing messages.',
            'This can be the same as the quotation mark character itself.'),
        ('quot_char', character, '"', 'quotation mark',
            'The character to use for quoting strings when printing messages.'),
    )
class SyntaxOptions(Configuration):
    ''' Options needed by this configuration script.'''
    __section__ = 'syntax'
    __options__ = (
        # os.path.abspath(__file__) would be useful here.
        ('variant_file', file, os.path.join('docs', 'variants.html'), 'variants file',
            'Document listing the available map variants, with their names and files.'),
        ('dcsp_file', file, os.path.join('docs', 'protocol.html'), 'protocol file',
            'Document specifying protocol information, including token names and numbers.'),
        ('syntax_file', file, os.path.join('docs', 'syntax.html'), 'syntax file',
            'Document specifying syntax rules and level names.'),
        
        # It would be nice if the tokens themselves contained this information.
        ('move_phases', list, ('SPR','FAL'), 'move phases',
            'Tokens that indicate movement phases'),
        ('retreat_phases', list, ('SUM','AUT'), 'retreat phases',
            'Tokens that indicate retreat phases'),
        ('build_phases', list, ('WIN',), 'build phases',
            'Tokens that indicate build phases'),
        
        # I might want to check sometime that these are powers of two
        ('move_phase_bit', int, 0x20, 'move order mask',
            'Bit that indicates movement phase in order token numbers.'),
        ('retreat_phase_bit', int, 0x40, 'retreat order mask',
            'Bit that indicates retreat phase in order token numbers.'),
        ('build_phase_bit', int, 0x80, 'build order mask',
            'Bit that indicates build phase in order token numbers.'),
    )
class GameOptions(Configuration):
    ''' Options sent in the HLO message.'''
    __section__ = 'game'
    __options__ = (
        ('LVL', int, 0, 'syntax level',
            'Syntax level of the game.',
            'Mostly determines what kind of press can be sent.',
            'See the message syntax document for more details.'),
        ('MTL', int, 0, 'Move Time Limit',
            'Time limit for movement phases, in seconds.',
            'A setting of 0 disables movement time limits.',
            'The standard "real-time" setting is 600 (five minutes).'),
        ('RTL', int, 0, 'Retreat Time Limit',
            'Time limit for retreat phases, in seconds.',
            'A setting of 0 disables retreat time limits.',
            'The standard "real-time" setting is 120 (two minutes).'),
        ('BTL', int, 0, 'Build Time Limit',
            'Time limit for build phases, in seconds.',
            'A setting of 0 disables build time limits.',
            'The standard "real-time" setting is 180 (three minutes).'),
        ('PTL', int, 0, 'Press Time Limit',
            'Time (in seconds) before movement deadlines to start blocking press.',
            'If there is no movement time limit, this has no effect;',
            'otherwise, if this is greater than or equal to MTL,',
            'press is entirely blocked in movement phases.'),
        
        ('NPR', bool, False, 'No Press during Retreats',
            'Whether press is blocked during retreat phases.'),
        ('NPB', bool, False, 'No Press during Builds',
            'Whether press is blocked during build phases.'),
        ('DSD', bool, False, 'Deadline Stops on Disconnection',
            'Whether time limits pause when a non-eliminated player disconnects.',
            'The standard "real-time" setting is yes.'),
        ('AOA', bool, False, 'Any Orders Allowed',
            'Whether to accept any syntactically valid order, regardless of legality.',
            "This server is more permissive than David's in AOA games;",
            "the latter doesn't accept orders for non-existent or foreign units.",
            'See also DATC option 4.E.1, which only comes up in AOA games.',
            'The standard "real-time" setting is no.'),
        ('PDA', bool, False, 'Partial Draws Allowed',
            "Whether to allow draws that don't include all survivors.",
            'When this is on, clients can specify powers to allow in the draw,',
            'and the server can specify the powers in a draw.',
            'Only available at syntax level 10 or above.'),
    )
    
    def __init__(self):
        self.__super.__init__()
        self.sanitize()
    def parse_message(self, message):
        ''' Collects the information from a HLO or LST message.'''
        for var_opt in message.fold()[-1]:
            if   len(var_opt) == 1: setattr(self, var_opt[0].text, True)
            elif len(var_opt) == 2: setattr(self, var_opt[0].text, var_opt[1])
            else:
                raise ValueError('Unknown variant option in %s message' %
                        message[0].text)
            
    def sanitize(self):
        ''' Performs a few sanity checks on the options.'''
        # Todo: Ensure that all numbers are positive.
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
    def tokenize(self):
        from language import Message
        return Message(self.get_params())
    
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


class Configurable(object):
    ''' Generic class for anything that can be configured by pydip.cfg files.
        __options__ and __section__ will be used to build a Configuration
        instance for each Configurable instance, which will be available
        as self.options.
    '''#'''
    __metaclass__ = autosuper
    def __init__(self):
        self.options = Configuration()
        self.options.parse_options(self.__class__)

class VerboseObject(Configurable):
    ''' Basic logging system.
        Provides one function, log_debug, to print lines either to stdout
        or to a configurable file, based on verbosity level.
        Classes or instances may override prefix to set the label on each
        line written by that item.
    '''#'''
    __files = {}
    __section__ = 'main'
    __options__ = (
        ('verbosity', int, 1, 'v',
            'How much debug or logging information to display.'),
        ('log_file', file, None, None,
            'File in which to log output lines, instead of printing them.'),
    )
    
    def log_debug(self, level, line, *args):
        if level <= self.options.verbosity:
            line = self.prefix + ': ' + str(line) % args
            filename = self.options.log_file
            if filename:
                output = self.__files.get(filename)
                if not output:
                    output = file(filename, 'a')
                    self.__files[filename] = output
                output.write(line + os.linesep)
            else:
                try: print line + '\n',
                except IOError: self.verbosity = 0 # Ignore broken pipes
    @settable_property
    def prefix(self): return self.__class__.__name__

class MapVariant(VerboseObject):
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
        self.__super.__init__()
        self.prefix      = '%s(%r)' % (self.__class__.__name__, variant_name)
        self.variant     = variant_name
        self.map_name    = variant_name.lower()
        self.description = description
        self.files       = files
        self.rep         = rep or self.get_representation()
        self.seasons     = [SPR, SUM, FAL, AUT, WIN]
        self.msg_cache  = {}
    def new_judge(self, game_options):
        from judge import Judge
        return Judge(self, game_options)
    def get_representation(self):
        filename = self.files.get('rem')
        if filename: return parse_file(filename, read_representation_file)
        else: return protocol.default_rep
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
    
    @settable_property
    def names(self):
        ''' Attempts to read the country and province names from a file.
            No big deal if it fails, but it's a nice touch.
        '''#'''
        names = {}
        try: name_file = self.open_file('nam')
        except (KeyError, IOError): return names
        else:
            try:
                from language import UNO
                for line in name_file:
                    fields = line.strip().split(':')
                    if fields[0]:
                        token = self.rep[fields[0].upper()]
                        if token.is_province():
                            names[token] = fields[1]
                        elif token.is_power() or token is UNO:
                            names[token] = (fields[1], fields[2])
                        else:
                            self.log_debug(11,
                                    "Unknown token type for %r", token)
            except Exception, err:
                self.log_debug(1, "Error parsing name file: %s", err)
            else: self.log_debug(11, "Name file loaded")
            name_file.close()
        self.names = names
        return names

# File parsing
def parse_file(filename, parser):
    result = None
    try: stream = open(filename, 'rU', 1)
    except IOError, err:
        raise IOError("Failed to open configuration file %r %s" %
                (filename, err.args))
    try: result = parser(stream)
    finally: stream.close()
    return result

def parse_variants(stream):
    name_pattern = re.compile('<td>(\w[^<]*)</td><td>(\w+)</td>')
    file_pattern = re.compile("<a href='([^']+)'>(\w+)</a>")
    descrip = name = None
    for line in stream:
        match = name_pattern.search(line)
        if match:
            descrip, name = match.groups()
            files = {}
        elif name and descrip:
            match = file_pattern.search(line)
            if match:
                ref, ext = match.groups()
                files[ext.lower()] = os.path.normpath(os.path.join(
                    os.path.dirname(options.variant_file), ref))
            elif '</tr>' in line:
                variants[name] = MapVariant(name, descrip, files)
                descrip = name = None

class Protocol(VerboseObject):
    ''' Collects various constants from the Client-Server Protocol file.
        Rather dependent on precise formatting.
        
        >>> proto = Protocol('docs/protocol.html')
        >>> proto.token_cats[0x42]
        'Unit Types'
        >>> proto.token_cats['Unit_Types']
        66
        >>> proto.error_strings[5]
        'Version incompatibility'
        >>> proto.default_rep[0x4101]
        ENG
        >>> proto.base_rep[0x481C]
        YES
        >>> proto.message_types['Diplomacy']
        2
    '''#'''
    def __init__(self, filename):
        self.base_rep = None
        self.default_rep = None
        self.token_cats = {}
        self.error_strings = {}
        self.message_types = {}
        self.version = None
        self.magic = None
        
        try: dcsp_file = open(filename, 'rU', 1)
        except IOError:
            raise IOError("Failed to open protocol file '%s'" % filename)
        else:
            try: self.parse_dcsp(dcsp_file)
            finally: dcsp_file.close()
        
        # Calculated constants needed by the language module
        # Todo: Move these to a more appropriate place
        TokenOptions.max_token = (max([cat for cat in self.token_cats.keys()
            if isinstance(cat, int)]) + 1) << 8
        TokenOptions.quot_prefix = self.token_cats['Text'] << 8
        TokenOptions.max_pos_int = (self.token_cats['Integers'][1] + 1) << 7
        TokenOptions.max_neg_int = TokenOptions.max_pos_int << 1
    
    def parse_dcsp(self, dcsp_file):
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
                    self.error_strings[err_type] = match.group(1)
                    err_type = None
                    old_line = ''
                else: old_line = line[line.rfind('>'):].strip()
            elif msg_name:
                if line.find('Message Type =') > 0:
                    type_num = int(re.match('.*Type = (\d+)', line).group(1))
                    self.message_types[msg_name] = type_num
                    msg_name = ''
            elif line.find(' (0x') > 0:
                match = re.match('.*?[> ](\w[\w ]+) \((0x\w\w)', line)
                descrip = match.group(1)
                start_cat = int(match.group(2), 16)
                match = re.match('.* (0x\w\w)\)', line)
                if match:
                    last_cat = int(match.group(1), 16)
                    self.token_cats[descrip.replace(' ', '_')] = (start_cat, last_cat)
                    for i in range(start_cat, last_cat + 1):
                        self.token_cats[i] = descrip
                else:
                    rep_item = descrip == 'Powers'
                    last_cat = start_cat << 8
                    self.token_cats[descrip.replace(' ', '_')] = start_cat
                    self.token_cats[start_cat] = descrip
            elif last_cat:
                if line.find('category =') > 0:
                    # This must come before the ' 0x' search.
                    match = re.match('.*>([\w -]+) category = (0x\w\w)<', line)
                    if match:
                        last_cat = int(match.group(2), 16)
                        self.token_cats[last_cat] = descrip = match.group(1)
                        self.token_cats[descrip.replace(' ', '_')] = last_cat
                        rep_item = True
                        last_cat <<= 8
                    else:
                        self.log_debug(1, 'Bad line in protocol file: ' + line)
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
                if match: self.version = int(match.group(1))
            elif line.find('Magic Number =') > 0:
                match = re.search('Number = (0x\w+)', line)
                if match: self.magic = int(match.group(1), 16)
                else: self.log_debug(1, 'Invalid magic number: ' + line)
        self.base_rep = Representation(token_names, None)
        self.default_rep = Representation(default_tokens, self.base_rep)
        
        # Sanity checking
        if not self.magic: self.log_debug(1, 'Missing magic number')
        if not self.version: self.log_debug(1, 'Missing version number')

def read_representation_file(stream):
    ''' Parses a representation file.
        The first line contains a decimal integer, the number of tokens.
        The remaining lines consist of four hex digits, a colon,
        and the three-letter token name.
        
        >>> rep = parse_file('variants/sailho.rem', read_representation_file)
        >>> rep['NTH']
        Token('NTH', 0x4100)
        
        # This used to be 'Psy'; it was probably changed for consistency.
        >>> rep[0x563B]
        Token('PSY', 0x563B)
        >>> len(rep)
        64
    '''#'''
    num_tokens = int(stream.readline().strip())
    if num_tokens > 0:
        rep = {}
        for line in stream:
            number = int(line[0:4], 16)
            name = line[5:8]
            uname = name.upper()
            if protocol.base_rep.has_key(uname):
                raise ValueError, 'Conflict with token ' + uname
            rep[number] = uname
            num_tokens -= 1
        if num_tokens == 0: return Representation(rep, protocol.base_rep)
        else: raise ValueError, 'Wrong number of lines in representation file'
    else: return protocol.default_rep


# Exporting variables
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
    opts = options
    
    # Masks to determine whether an order is valid during a given phase
    opts.order_mask = mask = {
        None: opts.move_phase_bit|opts.retreat_phase_bit|opts.build_phase_bit
    }
    
    # Export variables into the language globals
    import language
    language.Token.cats = protocol.token_cats
    language.Token.opts = protocol.base_rep.opts
    #print 'Attempting to add tokens to language...'
    for name, token in protocol.base_rep.items():
        #print 'Adding language.%s' % (name,)
        setattr(language, name, token)
        if   name in opts.move_phases:    mask[token] = opts.move_phase_bit
        elif name in opts.retreat_phases: mask[token] = opts.retreat_phase_bit
        elif name in opts.build_phases:   mask[token] = opts.build_phase_bit
    
    parse_file(opts.variant_file, parse_variants)

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
        'default_rep': protocol.default_rep,
        'base_rep': protocol.base_rep,
    }
    for name,token in opts.rep.items(): extension[name] = token
    extension.update(globs)
    return extension

# Global variables
options = SyntaxOptions()
protocol = Protocol(options.dcsp_file)
variants = {}

# Main initialization
init_language()
