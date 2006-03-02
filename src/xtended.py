''' PyDip standard name environment
    Copyright (C) 2004-2006 Eric Wald
    Licensed under the Open Software License version 3.0
    
    The standard map, default map tokens, and starting position messages.
    This module takes several seconds to load, and might not work properly,
    but offers a convenient way to import all those names.
'''#'''

import config, xtended
for key, value in config.extend_globals({}).iteritems():
    setattr(xtended, key, value)
