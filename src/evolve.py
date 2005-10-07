import config
from server    import Server
from player    import Player
from random    import randint
from threading import Thread
from time      import sleep

game_number = 0
def evolve(player_class, file_name):
	''' Modified main() for evolutionary programming.
	'''#'''
	global game_number
	next_values = None
	log_file = open(file_name, 'a', 1)
	options = {
		'verbosity': 0,
	}
	
	threads = []
	bored = False
	while not bored:
		# Start a new server
		server = Server(options)
		server_thread = Thread(target=server.run)
		server_thread.start()
		game_number += 1
		
		# Create the specified clients
		clients = server.local_connections(player_class, 0)
		players = []
		for client in clients:
			if client.open():
				if next_values: client.player.set_values(next_values.pop())
				players.append(client.player)
				new_thread = Thread(target=client.player_loop)
				threads.append((new_thread, client))
				new_thread.start()
			else: raise IOError, 'Client refuses to open.'
		
		# Create the gene splicing player
		client = server.local_connections(Gene_Splicer, 1)[0]
		if client.open():
			splicer = client.player
			new_thread = Thread(target=client.player_loop)
			threads.append((new_thread, client))
			new_thread.start()
		else: raise IOError, 'Client refuses to open.'
		
		# Wait for all threads to terminate.
		try:
			while server_thread.isAlive(): sleep(1)
		except KeyboardInterrupt:
			print 'Interrupted.  Closing server...'
			server.close()
			while server_thread.isAlive(): sleep(.1)
			bored = True
		while threads:
			thread,client = threads.pop()
			if bored and thread.isAlive(): client.close()
			try:
				while thread.isAlive(): sleep(.1)
			except KeyboardInterrupt:
				print 'Interrupted.  Closing client...'
				client.close()
				while thread.isAlive(): sleep(.1)
				bored = True
			# Last call for messages
			for msg in client.recv_list():
				client.player.handle_message(msg)
		
		# Find values for the next run
		next_values = splicer.get_next_values(players, log_file)
	log_file.close()
	print 'Goodbye.'

class Gene_Splicer(Player):
	''' An observer to collect winner information.
	'''#'''
	
	def __init__(self, *args):
		Player.__init__(self, *args)
		self.winners = []
	
	def handle_DRW(self, message):
		print message
		if len(message) > 3: self.winners = message[2:-1]
		else:                self.winners = map.current_powers()
	def handle_SLO(self, message):
		print message
		self.winners = [message[2]]
	def handle_SCO(self, message):
		print 'Game #%d, %s: %s' % (
			game_number,
			self.map.current_turn.year or 'start',
			message
		)
	
	def get_next_values(self, players, log_file):
		win_values = []
		log_file.write("Players in %s, ended in %s:\n"
			% (self.map.name, self.map.current_turn))
		for player in players:
			values = player.get_values() 
			token = player.power.token
			if token in self.winners:
				intro = '- Winner: '
				win_values.append(values)
			else: intro = '- Loser:  '
			log_file.write("%s%s as %s\n" % (intro, values, token))
		
		if win_values: cycles = len(players) // len(win_values)
		else: cycles = 0
		result = win_values[:]
		cycles -= 1
		if cycles > 1:
			result += [self.mutate(val_set, 0.4) for val_set in win_values]
			cycles -= 1
		while cycles > 0:
			result += [self.mutate(val_set, 0.05) for val_set in win_values]
			cycles -= 1
		return result
	def mutate(self, value_list, factor):
		def tweak(value):
			x = int(abs(value * factor)) + 1
			return value + randint(-x,x)
		return [tweak(value) for value in value_list]


if __name__ == "__main__":
	import dumbbot
	evolve(dumbbot.DumbBot, 'log/stats/evolution')
