''' PyDip standard name environment
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
    
    The standard map, default map tokens, and starting position messages.
    This module can take a few seconds to load, and might not work properly,
    but offers a convenient way to import all those names.
'''#'''

from sys       import modules

from config    import variants
from gameboard import Map
from language  import protocol

__all__ = ['standard_map', 'standard_sco', 'standard_now',
        'default_rep', 'base_rep']

# Standard map and its various attendants
opts = variants['standard']
standard_map = Map(opts)
standard_sco = opts.start_sco
standard_now = opts.start_now
default_rep = protocol.default_rep
base_rep = protocol.base_rep

# Tokens of the standard map
module = modules[__name__]
for name, token in default_rep.items():
    setattr(module, name, token)
__all__.extend(default_rep.keys())
