''' Human interfaces for Python Daide clients.
	Portions of Telnet adapted from J. Strout's simple chat server:
		http://www.strout.net/
'''
from __future__ import generators
from player import Player
from language import *
from time import sleep
import re

class Human(Player):
	''' Menu system to interact with a human player.
		
		The I/O routines get_string(self, prompt) and show_line(self, line)
		are very rudimentary, and should be overridden by subclasses.
	'''
	version = 'Python Human client'
	
	# These two routines should be overridden
	def get_string(self, prompt):
		# Return the first option, if we can find it
		result = re.sub('^.*\((.*?)(,|\)).*$', '\\1', prompt)
		if result: return result
		else:      return '1'
	def show_line(self, line):
		pass
	
	def __init__(self, *args):
		"Creates a new Human interface, ready to begin a server session."
		Player.__init__(self, *args)
		self.next_menu = self.get_player_type
		self.new_mail  = False
		self.time      = 0
		
	def read(self):
		'Produces a list of messages to return to the server, or None.'
		return self.next_menu()
	
	def select_option(self, prompt, option_list):
		''' Presents the user with a list of choices.
			option_list should be a series of series;
			the first of each will be printed with the prompt,
			and the last will be returned if the answer matches any.
		'''
		# Short-circuit when there's no choice
		if len(option_list) == 1: return option_list[0][-1]
		elif len(option_list) < 1: raise EmptyListError
		
		prompt += ' (' + ', '.join([opt[0] for opt in option_list]) + '): '
		while True:
			line = self.get_string(prompt).strip()
			for item in option_list:
				if line in item: return item[-1]
			else: self.show_line('Unrecognized option "' + line + '"')
	
	def select_tokens(self, prompt, token_list, limit=-1):
		''' Presents the user with a list of tokens, requesting
			any number of them (up to limit, if positive) in return.
			The tokens must be in string format.
		'''
		# Short-circuit when there's no choice
		if len(token_list) == 1: return token_list[0]
		elif len(token_list) < 1: raise EmptyListError
		
		prompt += ' (' + ', '.join(token_list) + '): '
		while True:
			selected = []
			for word in re.split(',?\s*', self.get_string(prompt)):
				if word not in token_list:
					self.show_line('Unrecognized token "' + word + '"')
					break
				else: selected.append(word)
			else:
				if limit > 0: return selected[:limit]
				else: return selected
	
	def get_number(self, prompt, min=None, max=None):
		''' Prompts the user to input a number,
			repeating until it's properly formatted.
			min and max limit the allowed range.
		'''
		while True:
			line = self.get_string(prompt)
			try:
				n = int(line.strip())
			except ValueError:
				self.show_line('Not a valid integer: "' + line + '"')
			else:
				if min != None and n < min:
					self.show_line('The number must be greater than ' + min)
				elif max != None and n > max:
					self.show_line('The number must be less than ' + max)
				else:
					return n
	
	def get_player_type(self):
		"Ask the user whether to be a new player, an observer, or an existing player."
		self.show_line('Welcome to a new game.')
		while True:
			answer = self.select_option('Do you want to be ',
				('a new player', 'P', 'p'), ('an observer', 'O', 'o'),
				('an existing country', 'C', 'c'), ('quit', 'Q', 'q'))
			if answer == 'p':
				message = NME(self.get_string('Enter your name: '), self.version)
			elif answer == 'o':
				message = OBS()
			elif answer == 'c':
				message = IAM(self.select_tokens(self.map.powers, 1),
					self.get_number('Enter your passcode: '))
			elif answer == 'q':
				self.show_line('Goodbye.')
				self.close()
			else:
				raise IllegalStateError
			yield message
			
			while True:
				reply = self.dequeue_message(message[0])
				if reply:
					if reply[0] == YES:
						show_line('Application accepted.  Waiting for map...')
					else:
						show_line('Application rejected.')
						# Run through the menu loop again...
					break
				else: yield []


class Console(Human):
	''' Uses the console to perform user I/O.
		Only one of these may be instantiated at a time.
	'''
	version = 'Python Console client'
	
	def get_string(self, prompt): return raw_input(prompt)
	def show_line(self, line): print line


class Telnet(Human):
	''' Listens for a telnet connection, for user I/O.
		This client would definitely benefit from a separate thread,
		but not a separate process.
	'''
	_sock = None
	_newline = "\r\n"
	options = Human.options + (
		'telnet_port', int, 'telnet port', 16714)
		'telnet_host', str, 'telnet host', '')
	)
	
	def __init__(self, *args):
		Human.__init__(self, *args)

		# Create the shared socket, if necessary
		if not Telnet._sock:
			from socket import socket, AF_INET, SOCK_STREAM
			import config
			sock = socket(AF_INET, SOCK_STREAM)
			sock.bind((config.client_options.telnet_host, config.client_options.telnet_port))
			sock.setblocking(True)
			sock.listen(5)
			Telnet._sock = sock

		# Wait for a connection
		self.conn, addr = Telnet._sock.accept()
		self.conn.setblocking(False)
		self.firstline = True
		self.version = 'Python Telnet client, connected from ' + ':'.join(map(str, addr))
	
	def get_string(self, prompt):
		net = self.conn
		net.send(prompt)
		data = ''
		while not data:
			sleep(.5)		# sleep to reduce processor usage
			data = net.recv(1024)
			# try to trap garbage initially sent by some telnets:
			if self.firstline:
				if len(data) < 2:
					net.send(prompt)
					data = ''
				else:
					self.firstline = False
		return data
	
	def show_line(self, line):
		self.conn.send(line + self._newline)
	
	def close(self):
		Player.close(self)
		self.conn.close()

'''
> initial
	< representation : connected

connected:
any > NME () ()
	either < YES ()
		< MAP ()
		maybe > MDF
			< MDF () () ()
		either > YES ()
			< HLO () () () : player
		or > REJ () : connected
	or < REJ () : connected
or > OBS
	either < YES ()
		< MAP ()
		maybe > MDF
			< MDF () () ()
		either > YES () : observer
		or > REJ () : connected
	or < REJ () : connected
or > IAM () ()
	either < YES () : player
	or < REJ () : connected


'''
