import config
"""
from threading import Thread
from time      import sleep
from sys       import argv

class External_Server(Client_Manager):
	def __init__(self, *args):
		self.__super.__init__(*args)
		client = Remote(player_class=Tournament_Director, host=opts.host, port=opts.port)
class Tournament_Director(Observer):
	name = 'Client Manager'
	def __init__(self, *args):
		self.__super.__init__(*args)

def main(option_dict):
	'''	Initializes the requested services, and binds them together.'''
	from network import Remote
	threads = []
	config.option_class.local_opts.update(option_dict)
	opts = main_options()
	reserved = 0
	server = None
	
	if opts.internal:
		from server      import Server
		server = Server()
		if opts.network: server.start_service(opts.host, opts.port)
		server_thread = Thread(target=server.run)
		server_thread.start()
	if server:
		try:
			while server_thread.isAlive(): sleep(1)
		except KeyboardInterrupt:
			server.close();
			bored = True
			while server_thread.isAlive(): sleep(1)
	while threads:
		thread,client = threads.pop()
		if bored and thread.isAlive(): client.close()
		while thread.isAlive():
			try: sleep(.1)
			except KeyboardInterrupt: client.close(); bored = True

def run_player(player_class):
	try:
		opts = {'clients': [player_class]}
		for arg in argv:
			try: num = int(arg)
			except ValueError:
				if arg[3] == '=':
					opts.setdefault('countries', {})[arg[:3]] = int(arg[4:])
				elif opts.has_key('host'): raise ValueError
				else:
					index = arg.find(':')
					if index >= 0:
						opts['host'] = arg[:index]
						opts['port'] = arg[index+1:]
					else: opts['host'] = arg
			else: opts['clients'] *= num
		else: opts['host'] = 'localhost'
	except:
		print 'Usage: %s [host][:port] [number] [power=passcode] ...' % argv[0]
		print 'Connects <number> copies of %s to <host>:<port>' % (player_class.name or player_class.__name__)
	else: main(opts)

def run_realtime():
	main({
		'clients': [],
		'internal': True,
		'takeover': True,
		'quit': False,
		'verbosity': 4,
		'games': 0,
		'variant': 'standard',
		'MTL': 300, 'BTL': 180, 'RTL': 120, 'DSD': True,
	})
	print 'Thank you for playing.'
"""#"""

def run_player(player_class, allow_multiple=True, allow_country=True):
    from sys     import argv
    from network import Client
    name = player_class.name or player_class.__name__
    num = 1
    try:
        opts = allow_country and {'countries': {}} or {}
        for arg in argv[1:]:
            try: num = int(arg)
            except ValueError:
                if arg[3] == '=': opts['countries'][arg[:3]] = int(arg[4:])
                elif opts.has_key('host'): raise ValueError
                else:
                    index = arg.find(':')
                    if index >= 0:
                        opts['host'] = arg[:index]
                        opts['port'] = int(arg[index+1:])
                    else: opts['host'] = arg
            else:
                if not allow_multiple: raise ValueError
        else: opts['host'] = 'localhost'
    except:
        if allow_multiple:
            print 'Usage: %s [host][:port] [number]%s' % (argv[0],
                    allow_country and ' [power=passcode] ...' or '')
            print 'Connects <number> copies of %s to <host>:<port>' % name
        else:
            print 'Usage: %s [host][:port]%s' % (argv[0],
                    allow_country and ' [power=passcode]' or '')
            print 'Connects a copy of %s to <host>:<port>' % name
    else:
        if num == 1:
            config.option_class.local_opts.update(opts)
            client = Client(player_class)
            if client.open(): client.run()
            else: print '%s refuses to run.  Sorry.' % name
        else:
            from time import sleep
            bored = False
            threads = []
            for dummy in range(num):
                client = Client(player_class)
                thread = client.start()
                if thread: threads.append((thread, client))
                else: print 'Failed to start %s.  Sorry.' % name
            for thread, client in threads:
                if bored and thread.isAlive(): client.close()
                while thread.isAlive():
                    try: sleep(.1)
                    except KeyboardInterrupt: client.close(); bored = True

def run_server():
    from functions import Verbose_Object
    from network   import ServerSocket
    Verbose_Object.verbosity = 7
    server = ServerSocket()
    if server.open(): server.run()
    else: server.log_debug(1, 'Failed to open.')

if __name__ == "__main__":
	run_server()
	#import player
	#if len(argv) > 1: run_player(player.Echo)
	#else: run_realtime()

# vim: ts=4 sw=4 noet
