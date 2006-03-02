from sys import argv
import config

def run_player(player_class, allow_multiple=True, allow_country=True):
    from network   import Client
    from functions import Verbose_Object
    name = player_class.name or player_class.__name__
    num = 1
    opts = {}
    countries = {}
    try:
        for arg in argv[1:]:
            try: num = int(arg)
            except ValueError:
                if arg[3] == '=':
                    if allow_country: countries[arg[:3]] = int(arg[4:])
                    else: raise ValueError
                elif arg[:2] == '-v': Verbose_Object.verbosity = int(arg[2:])
                elif arg[0] == '-' or opts.has_key('host'): raise ValueError
                else:
                    index = arg.find(':')
                    if index >= 0:
                        opts['host'] = arg[:index]
                        opts['port'] = int(arg[index+1:])
                    else: opts['host'] = arg
            else:
                if not allow_multiple: raise ValueError
    except:
        if allow_multiple:
            print 'Usage: %s [host][:port] [number]%s [-v<level>]' % (argv[0],
                    allow_country and ' [power=passcode] ...' or '')
            print 'Connects <number> copies of %s to <host>:<port>' % name
        else:
            print 'Usage: %s [host][:port]%s -v<level>' % (argv[0],
                    allow_country and ' [power=passcode]' or '')
            print 'Connects a copy of %s to <host>:<port>' % name
    else:
        config.option_class.local_opts.update(opts)
        if num == 1:
            if countries:
                nation, pcode = countries.popitem()
                client = Client(player_class, power=nation, passcode=pcode)
            else: client = Client(player_class)
            if client.open(): client.run()
            else: print '%s refuses to run.  Sorry.' % name
        else:
            from time import sleep
            bored = False
            threads = []
            while num > 0 or countries:
                num -= 1
                if countries:
                    nation, pcode = countries.popitem()
                    client = Client(player_class, power=nation, passcode=pcode)
                else: client = Client(player_class)
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
    verbosity = 7
    opts = {}
    try:
        for arg in argv[1:]:
            if arg[:2] == '-v': verbosity = int(arg[2:])
            elif arg[:2] == '-g':
                games = int(arg[2:])
                opts['games'] = games
                opts['number of games'] = games
            else:
                config.variants[arg]
                opts['variant'] = arg
                opts['default variant'] = arg
    except:
        print 'Usage: %s [-gGAMES] [-vLEVEL] [VARIANT]' % (argv[0],)
        print 'Serves GAMES games of VARIANT, with output verbosity LEVEL'
    else:
        config.option_class.local_opts.update(opts)
        Verbose_Object.verbosity = verbosity
        server = ServerSocket()
        if server.open(): server.run()
        else: server.log_debug(1, 'Failed to open the server.')

if __name__ == "__main__": run_server()

# vim: sts=4 sw=4 et tw=75 fo=crql1
