'''	The standard map, default map tokens, and starting position messages.
	This module takes several seconds to load, and might not work properly.
'''#'''

import config, xtended
for key, value in config.extend_globals({}).iteritems():
	setattr(xtended, key, value)

# vim: ts=4 sw=4 noet
