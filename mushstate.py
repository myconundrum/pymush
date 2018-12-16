
from server import MudServer
import database
from database import ObjectFlags
import bcrypt
import os.path
import pickle
import time
import queue
import fnmatch

_BASE="data"
_LOG="log.txt"
_LOGLEVEL=2
_GODPASS = "godpass"
_PERIODIC_UPDATE = 60
_MUSHNAME 				= "PynnMush"
_MUSHVERSION			= 1.02

_WELCOMEMSG = f"""
=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=		
Welcome to {_MUSHNAME} {_MUSHVERSION}!					     
connect <name> : connect to existing player with name <name>        
create <name>  : create a new player with name <name>               
=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=		
"""


class Command:
	def __init__(self,dbref,cmd,args):
		self.dbref = dbref
		self.cmd = cmd
		self.args = args
	

class UserRecord:

	def __init__(self):

		self.hash = None
		self.dbref = None
		self.first = None 
		self.last = None

class MushState:

	def __init__(self):
		self.users = {}	 				# user/password database
		self.version = 	_MUSHVERSION

		self.running 	= False			# is mush currently running?
		self.pidToDbref = {}			# look up from networking pid table for connected players
		self.dbrefToPid = {}			# look up from dbref to networking pid for connected players

		self.server = None 				# mush networking code

		self.logLevel = _LOGLEVEL		# what events are captured for logging		
		self.logFile = open(_LOG,"w")
		self.lastPeriodic = 0
		self.lastSave = 0				# last time saved. 
		self.startTime = time.time()
		self.db  = database.Database()
		self.freshMush()

		self.commandQueue = queue.Queue() # indirect commands get added to the command queue.
		self.playerQueue = queue.Queue()  # player direct commands get added to the player Queue.

	def start(self):

		
		self.log(0,"=== Mush started.")
		self.running = True 		
		self.server = MudServer()
		self.lastPeriodic = time.time()
		self.load(_BASE)

		
	def quit(self):

		self.log(0,"==== Mush Exiting.")
		self.logFile.close()
		self.running = False
		self.server.shutdown()
		self.save(_BASE)
		
	def update(self):

		
		self.server.update()
		# account for new players
		for pid in self.server.get_new_players():
			self.pidToDbref[pid] = -1
			self.server.send_message(pid,_WELCOMEMSG)

   		# account for disconnecting players
		for pid in self.server.get_disconnected_players():
			self.db[self.pidToDbref[pid]].flags ^= ObjectFlags.CONNECTED
			self.db[self.pidToDbref[pid]].flags ^= ObjectFlags.DARK

			del self.dbrefToPid[self.pidToDbref[pid]]
			del self.pidToDbref[pid]

		if (time.time() - self.lastPeriodic > _PERIODIC_UPDATE):
			self.log(1,"Doing periodic updates...")
			self.db.recycle()
			self.lastPeriodic = time.time()


		#handle user input.
		self.handleInput()


	def message(self,dbref,msg,ignore=-1):

		o = mush.db[dbref]
		
		# send actual message to the console of a connected player.
		if (o.flags & ObjectFlags.CONNECTED): 
			self.server.send_message(self.dbrefToPid[dbref],msg)

		# check to see if there is a LISTEN attribute that matches this.
		if "LISTEN" in o and (fnmatch.fnmatch(msg,o["LISTEN"])):
			for action in ("" if not "AHEAR" in o else o["AHEAR"]).split(";"):
				action = action.split(" ",1)
				self.commandQueue.put(Command(o.dbref,action[0].upper(),action[1]))

		# this is a room. send the message to the contents of the room.
		if o.flags & ObjectFlags.ROOM:
			for dbref in [x for x in o.contents if x != ignore]:
				self.message(dbref,msg)


	def messageAll(self,msg):
		for dbref in mush.dbrefToPid:
			self.message(dbref,msg)

	def handleInput(self):
		
		for data in self.server.get_commands():
			(pid, cmd, args) = data 
			# catch empty input.
			if (len(cmd) == 0):
				continue

			# handle connecting players.
			if (self.pidToDbref[pid] == -1):
				self.handleConnectingPlayer(pid,cmd,args)
				continue 

			# special case some commands that don't end in a whitespace.
			if (cmd[0] == ':'): 
				args = f"{cmd[1:]} {args}"
				cmd = ':'
			elif (cmd[0] == ';'):
				args = f"{cmd[1:]} {args}"
				cmd = ';'
			elif (cmd[0] == '"'):
				args = f"{cmd[1:]} {args}"
				cmd = '"'
		
			# upper case the command to do proper matching and then enqueue the results.
			cmd = cmd.upper()
			self.playerQueue.put(Command(self.pidToDbref[pid],cmd,args))


	def handleConnectingPlayer(self,pid,cmd,args):

		cmd = cmd.upper()
		if (cmd == "CONNECT"):
			l = args.split(" ",1)

			if not self.userExists(l[0]):
				self.server.send_message(pid,"Bad username or password. Try again.")
				return 

			if (len(l) == 1):
				self.server.send_message(pid,"No password. Try again.")
				return 

			if not self.connectUser(l[0],pid,l[1]):
				self.server.send_message(pid,"Bad username or password. Try again.")
				return 

			p = self.db[self.pidToDbref[pid]]
			p.flags |= ObjectFlags.CONNECTED
			p.flags ^= ObjectFlags.DARK
			self.message(p.location,f"{p.name} connected.")
			self.log(1,f"{p.name} (#{p.dbref}) connected.")
			self.playerQueue.put(Command(p.dbref,"LOOK",""))

		if (cmd == "CREATE"):
			l = args.split(" ",1)

			if self.userExists(l[0]):
				self.server.send_message(pid,"That name already exists. Choose another.")
				return 

			if (len(l)==1):
				self.server.send_message(pid,"No password. Try again.")
				return 
			
			# create a new player object in the game
			dbref = self.db.newPlayer(None)
			self.db[dbref]["NAME"] = l[0]
			self.db[dbref].flags |= ObjectFlags.CONNECTED
			self.db[dbref].location = self.db.playerBase
			self.db[self.db.playerBase].contents.append(dbref)

			self.newUser(dbref,pid,l[1])
			self.message(self.db[dbref].location,f"Character named {self.db[dbref].name} created.")
			self.playerQueue.put(Command(dbref,"LOOK",""))
			self.log(1,f"New user created named {self.db[dbref].name} with dbref #{dbref}")
			

	def commandReady(self):
		return not self.playerQueue.empty() or not self.commandQueue.empty()

	def getCommand(self):
		if not self.playerQueue.empty():
			return self.playerQueue.get()
		if not self.commandQueue.empty():
			return self.commandQueue.get()

	def newUser(self,dbref,pid,password):

		key = self.db[dbref].name.upper()

		self.users[key] 		= UserRecord()
		self.users[key].dbref 	= dbref
		self.users[key].hash 	= bcrypt.hashpw(password.encode('utf8'), bcrypt.gensalt())	
		self.users[key].first 	= time.time()
		self.users[key].last 	= time.time()

		# save the network mapping tables between pid<->dbref
		if (pid != -1):
			self.pidToDbref[pid] 	= dbref
			self.dbrefToPid[dbref] 	= pid

	def connectUser(self,name,pid,password):

		name = name.upper()
		if not bcrypt.checkpw(password.encode('utf8'), self.users[name].hash):
			return False

		# save the network mapping tables between pid<->dbref
		self.pidToDbref[pid] 						= self.users[name].dbref
		self.dbrefToPid[self.users[name].dbref] 	= pid
		self.users[name].last = time.time()
		return True

	def disconnectUser(self,dbref):
		pid = self.dbrefToPid[dbref]
		self.pidToDbref[pid] = -1
		del self.dbrefToPid[dbref]
		self.server.send_message(pid,_WELCOMEMSG)

	def userExists(self,name):
		name = name.upper()
		return name in self.users

	def log(self,level,msg):
		if (level <= self.logLevel):
			print(f"{time.asctime()}: {msg}")
			self.logFile.write(f"{time.asctime()}: {msg}\n")

	def freshMush(self):

		self.db = database.Database()
		# Special objects cold start.
		self.db.masterRoom = self.db._newObject()
		o = self.db[self.db.masterRoom]
		o.dbref = self.db.masterRoom
		o = self.db[self.db.masterRoom]
		o["NAME"] = "Master Room"
		o["DESCRIPTION"] = "Around you swirls the formless energy of infinite possibility."
		o.owner = o.dbref 
		o.flags |= ObjectFlags.ROOM 
		o.location = o.dbref 


		# Special objects cold start.
		self.db.god = self.db.newPlayer(self.db[self.db.masterRoom])
		o = self.db[self.db.god]
		o["NAME"] = "God"
		o["DESCRIPTION"] = "The Alpha and Omega."
		o.owner = self.db.god  
		o.flags |= (ObjectFlags.GOD | ObjectFlags.DARK | ObjectFlags.WIZARD)
		o.location = self.db.masterRoom 
		self.db[self.db.masterRoom].contents.append(self.db.god)

		self.db.playerBase = self.db.newRoom(self.db[self.db.god])
		o = self.db[self.db.playerBase]
		o["NAME"] = "Player Base"
		o["DESCRIPTION"] = "A quiet room in the back of a bustling inn."

		# add password for god.
		self.newUser(self.db.god,-1,_GODPASS)

	def save(self,base):

		with open(f"{base}.dat","wb") as f:
			pickle.dump(self.version,f,pickle.HIGHEST_PROTOCOL)
			pickle.dump(time.time(),f,pickle.HIGHEST_PROTOCOL)
			pickle.dump(self.users,f,pickle.HIGHEST_PROTOCOL)
			pickle.dump(self.db,f,pickle.HIGHEST_PROTOCOL)


	def load(self,base):

		if not os.path.isfile(f"{base}.dat"):
			self.log(0,"Mush: data files not found. Starting fresh.")
			self.freshMush()
			return

		with open(f"{base}.dat","rb") as f:
			version 	= pickle.load(f)
			lastSave 	= pickle.load(f)
			users 		= pickle.load(f)
			db 			= pickle.load(f)

			if (version == self.version and db.version == database.latestVersion()):
				self.db = db 
				self.users = users 
				self.lastSave = lastSave
				self.log (0,f"Mush: Loaded {len(self.db)} objects and {len(self.users)} users from {base}.dat.")
			else: 
				self.log (0,f"Mush: failed to load {base}.dat. Version mismatch.")
				self.log (0,f"Mush version is {version} expected {self.version}")
				self.log (0,f"DB version is {db.version}. expected {self.db.version}.")
				self.log (0,f"Starting fresh.")
				self.freshMush()
				return

		# clear any connected flags.
		l = [d for d in self.db if (d.flags & (ObjectFlags.PLAYER | ObjectFlags.CONNECTED))]
		for d in l:
			d.flags ^= ObjectFlags.CONNECTED
			d.flags |= ObjectFlags.DARK

		# set any connected flags for logged in users.
		for dbref in self.dbrefToPid:
			self.db[dbref].flags |= ObjectFlags.CONNECTED
			self.db[dbref].flags ^= ObjectFlags.DARK


mush = MushState()

