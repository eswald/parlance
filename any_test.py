from main import main

import network, player, dumbbot, evilbot, combobot
if __name__ == "__main__":
	main({
		'clients': [
			#network.Fake_Player,
			#None,
			#None,
			#evilbot.EvilBot,
			#evilbot.EvilBot,
			#evilbot.EvilBot,
			#evilbot.EvilBot,
			#dumbbot.DumbBot,
			#dumbbot.DavidBot,
			#dumbbot.DavidBot,
			#combobot.ComboBot,
			player.HoldBot,
			#player.Clock,
			#player.Sizes,
			#player.Echo,
			#player.Ladder,
		],
		'fill': evilbot.EvilBot,
		#'fill': player.HoldBot,
		#'fill': dumbbot.DumbBot,
		#'host': '200.228.103.68',
		'internal': False,
		'network': True,
		'takeover': True,
		'quit': True,
		'verbosity': 4,
		'games': 1,
		#'variant': 'sailho',
		'variant': 'standard',
		#'variant': 'recovered',
		'MTL': 300, 'BTL': 180, 'RTL': 120, 'DSD': True,
	})
	print 'Thank you for playing.'

# vim: ts=4 sw=4 noet
