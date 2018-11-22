
from server import MudServer
import database
from database import ObjectFlags
import bcrypt
import os.path
import pickle
import time

_BASE="data"
_LOG="log.txt"
_LOGLEVEL=2
_GODPASS = "godpass"
_PERIODIC_UPDATE = 60
_MUSHNAME 				= "Farland"
_MUSHVERSION			= 1.01

_WELCOMEMSG = f"""
=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=		
Welcome to {_MUSHNAME} {_MUSHVERSION}!					     
connect <name> : connect to existing player with name <name>        
create <name>  : create a new player with name <name>               
=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=		
"""
	

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

		self.db = None 					# mush object database
		self.server = None 				# mush networking code

		self.logLevel = _LOGLEVEL		# what events are captured for logging
		self.logFile = None 			# log file destination
		self.lastPeriodic = 0



	def start(self):

		
		self.logFile = open(_LOG,"w")

		self.log(0,"=== Mush started.")

		self.running = True 		

		# initialize server
		self.server = MudServer()

		# intialize object database
		self.db  = database.Database()

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
			self.msgPid(pid,_WELCOMEMSG)

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

	


	def getCommands(self):
		return self.server.get_commands()

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
		self.msgPid(pid,_WELCOMEMSG)

	def userExists(self,name):
		name = name.upper()
		return name in self.users

	# Messaging helper functions
	def msgPid(self,pid,msg):
		self.server.send_message(pid,msg)

	def msgDbref(self,dbref,msg):
		if dbref in self.dbrefToPid:
			self.msgPid(self.dbrefToPid[dbref],msg)

	def msgLocation(self,dbref,msg,ignore=-1):
		l = [d for d in self.db[dbref].contents \
			if (d != ignore and self.db[d].flags & (ObjectFlags.PLAYER | ObjectFlags.CONNECTED))]

		for d in l:
			self.msgDbref(d,msg)

	def msgAll(self,msg):
		for pid in self.pidToDbref:
			self.msgPid(pid,msg)

	def log(self,level,msg):
		if (level <= self.logLevel):
			print(f"{time.asctime()}: {msg}")
			self.logFile.write(f"{time.asctime()}: {msg}\n")

	def freshMush(self):

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
			pickle.dump(self.version,f)
			pickle.dump(self.users,f,pickle.HIGHEST_PROTOCOL)
			pickle.dump(self.db,f,pickle.HIGHEST_PROTOCOL)


	def load(self,base):

		if not os.path.isfile(f"{base}.dat"):
			self.log(0,"Mush: data files not found. Starting fresh.")
			self.freshMush()
			return

		with open(f"{base}.dat","rb") as f:
			version 	= pickle.load(f)
			users 		= pickle.load(f)
			db 			= pickle.load(f)

			if (version == self.version and db.version == database.latestVersion()):
				self.db = db 
				self.users = users 
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

