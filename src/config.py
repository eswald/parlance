''' PyDip configuration management
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
    
    Harfs files for constants and other information.
    The main configuration files are pydip.cfg in the current working directory,
    and ~/.pydiprc in the user's home directory.
'''#'''

import re
from ConfigParser import RawConfigParser
from os           import linesep, path
from weakref      import WeakValueDictionary

from functions import autosuper, settable_property

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
    _user_config = RawConfigParser()
    _user_config.read(['pydip.cfg', path.expanduser('~/.pydiprc')])
    _local_opts = {}
    _configurations = WeakValueDictionary()
    
    def __init__(self):
        self.parse_options(self.__class__)
        self._configurations[id(self)] = self
    def parse_options(self, klass):
        for cls in reversed(klass.__mro__):
            section = cls.__dict__.get('__section__', cls.__module__)
            opts = cls.__dict__.get('__options__', ())
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
                    val = get(self, alt_names, section)
                    if val is not None: value = val
            elif alt_names:
                for item in alt_names:
                    if len(item) > 1:
                        val = get(self, item, section)
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

class SyntaxOptions(Configuration):
    ''' Options needed by this configuration script.'''
    __section__ = 'syntax'
    __options__ = (
        # path.abspath(__file__) would be useful here.
        ('variant_file', file, path.join('docs', 'variants.html'), 'variants file',
            'Document listing the available map variants, with their names and files.'),
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
        from tokens import LVL, MTL, RTL, BTL, AOA, DSD, PDA, NPR, NPB, PTL
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
        ('log_file', file, '', None,
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
                output.write(line + linesep)
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
        from tokens import SPR, SUM, FAL, AUT, WIN
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
        from language import protocol
        filename = self.files.get('rem')
        if filename: return parse_file(filename, read_representation_file)
        else: return protocol.default_rep
    def read_file(self, extension):
        result = self.msg_cache.get(extension)
        if not result:
            filename = self.files.get(extension)
            if filename:
                result = self.rep.read_message_file(filename)
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
                from tokens import UNO
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

class VariantDict(dict):
    ''' Simple way to avoid parsing the variants file until we need to.'''
    options = SyntaxOptions()
    
    def __getitem__(self, key):
        if not self: parse_file(self.options.variant_file, self.parse_variants)
        return dict.__getitem__(self, key)
    def parse_variants(self, stream):
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
                    files[ext.lower()] = path.normpath(path.join(
                        path.dirname(self.options.variant_file), ref))
                elif '</tr>' in line:
                    self[name] = MapVariant(name, descrip, files)
                    descrip = name = None

def read_representation_file(stream):
    ''' Parses a representation file.
        The first line contains a decimal integer, the number of tokens.
        The remaining lines consist of four hex digits, a colon,
        and the three-letter token name.
    '''#'''
    from language import Representation, protocol
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
def extend_globals(globs):
    ''' Inserts into the given dictionary elements required by certain doctests.
        Namely,
        - standard_map
        - standard_sco
        - standard_now
        - The default map tokens (ENG, NWY, etc.)
        
        This takes several seconds, so only do it if necessary.
    '''#'''
    from gameboard import Map
    from language import protocol
    opts = variants['standard']
    standard_map = Map(opts)
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
variants = VariantDict()
