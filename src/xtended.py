''' PyDip standard name environment
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
    
    The standard map, default map tokens, and starting position messages.
    This module takes several seconds to load, and might not work properly,
    but offers a convenient way to import all those names.
'''#'''

import sys
import config
module = sys.modules[__name__]
extended = config.extend_globals({})
for key, value in extended.iteritems():
    setattr(module, key, value)
__all__ = extended.keys()
