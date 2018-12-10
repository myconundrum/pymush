



from enum import Flag, auto, Enum
import time


_RECYCLE_WAIT = 300 # 5 minute wait before recycling.


NOTHING = -1



_DB_VERSION = 1.01
def latestVersion():
	return _DB_VERSION



#
# WARNING: If anything is done to this data structure other than appending a new flag to the end, the database version should be 
# updated as the reloaded flag values will be incorrect.
#
class ObjectFlags(Flag) :
	NOFLAG  		= 0

	# object has been deleted and is waiting to be recycled.
	JUNK    		= auto()
	
	# object type flags
	ROOM			= auto() 
	EXIT 			= auto()
	PLAYER 			= auto()

	# state flags
	CONNECTED		= auto()
	WIZARD 			= auto()
	GOD 			= auto()
	DARK			= auto()
	ENTER_OK		= auto()

class AttributeFlags(Flag) :
	NOFLAG 			= 0


class DbObject(dict) :

	def __init__(self):


		super(DbObject,self).__init__()


		self.dbref = NOTHING				 	# db ref for this object
		self.flags = ObjectFlags.NOFLAG 		# global flags
	

		self.location = NOTHING					# contains a dbref. definition varies by object type. 
												# if player or object, is the the location room
												# if exit, points to the destination
												# if room points to drop-to.

		self.contents = []						# list of dbrefs contained in this object

		self.owner = NOTHING					# owner dbref of this object
		self.home = NOTHING 					# home for this object...note, for EXITS, this will be the originating room.

		self.creationTime = time.time()			# object created...
		self.lastModified = time.time()			# object modified...
		self.destroyedTime = None 				# when was the object destroyed...used to decide when to recycle.


		self.exData  = {}						# Extended attribute information is stored here (owner, flags, etc)

		self.name = ""							# Name without aliases. 
		self.aliases = ""						
	
		self["NAME"] = "Nothing"
		self["DESCRIPTION"] = "You see nothing special."


	# This is necessary because dict has a custom pickler. Without having this __new__ and __getnewargs__ 
	# the extended attributes of our dictionary are not unpickled.
	def __new__(cls, *args, **kw):
		f = super().__new__(cls, *args, **kw)
		f.__init__()
		return f

	def __getnewargs__(self):
		return ()


	def __setitem__(self,key,value):
		key = key.upper()
		super(DbObject,self).__setitem__(key,value)

		self.exData[f"_{key}_owner"] = self.dbref
		self.exData[f"_{key}_flags"] = AttributeFlags.NOFLAG
		self.lastModified = time.time()
		if (key == "NAME"):
			self.aliases = value.split(';')
			self.aliasMatches = value.upper().split(';')
			self.name = self.aliases[0]

	def __delitem__(self,key):
		key = key.upper()
		super(DbObject,self).__delitem__(key)
		del self.exData[f"_{key}_owner"]
		del self.exData[f"_{key}_flags"]
		self.lastModified = time.time()
		
		# always have a name and description attribute.
		if (key == "NAME"):
			self["NAME"] = "Nothing"
		if (key == "DESCRIPTION"):
			self["DESCRIPTION"] = "You see nothing special."

	def getAttrOwner(self,key):
		return self.exData[f"_{key}_owner"]

	def getAttrFlags(self,key):
		return self.exData[f"_{key}_flags"]

	def setAttrOwner(self,key,dbref):
		key = key.upper()
		if key in self:
			self.exData[f"_{key}_owner"]=dbref
		self.lastModified = time.time()

	def setAttrFlags(self,key,flags):
		key = key.upper()
		if key in self:
			self.exData[f"_{key}_owner"]=flags
		self.lastModified = time.time()

	def aliasMatch(self,val):
		return val.upper() in self.aliasMatches

	def typeString(self):
		v = self.flags & (ObjectFlags.ROOM | ObjectFlags.EXIT | ObjectFlags.PLAYER)
		return v.name if v else "OBJECT"

	


class Database(list):

	
	def __init__(self):

		super(Database,self).__init__()

		self.version = _DB_VERSION  # used to validate pickle data.

		
		self.next = 0				# Next new dbref
		self.junk = []				# junk dbrefs, waiting to be recycled.
		self.recycled = []			# recycled dbrefs, ready to be reused. 

		self.masterRoom = NOTHING				# dbref of the master room.
		self.playerBase = NOTHING				# dbref of the player base.
		self.god = NOTHING 						# dbref of god.

		

	# This is necessary because dict has a custom pickler. Without having this __new__ and __getnewargs__ 
	# the extended attributes of our dictionary are not unpickled.
	def __new__(cls, *args, **kw):
		f = super().__new__(cls, *args, **kw)
		f.__init__()
		return f

	def __getnewargs__(self):
		return ()

	def __delitem__(self,dbref):

		o = self[dbref]
		
		# don't delete again if already marked junk.
		if (o.flags & ObjectFlags.JUNK):
			return 

		# Don't allow deletion if this object is one of several special objects (Master Room, God, etc)
		if (dbref == self.masterRoom or dbref == self.god or dbref == self.playerBase):
			return

		# get rid of contents. Destroy exits, send other items to their owner or home.
		for d in o.contents:
			# delete exits of a deleted room.
			if self[d].flags & ObjectFlags.EXIT:
				del self[d]

			# otherwise send objects home.
			if self[d].home == NOTHING or self[self[d].home].flags & ObjectFlags.JUNK: 
				self[self.masterRoom].contents.append(d)
			else:
				self[self[d].home].contents.append(d)

		o.contents = []

		# add to the junk list to be recycled.
		self.junk.append(dbref)
		o.flags |= ObjectFlags.JUNK

		# remove from the contents of its location.
		if (not o.flags & ObjectFlags.ROOM):
			self[o.home if o.flags & ObjectFlags.EXIT else o.location].contents.remove(dbref)



		# Now remove references to this room in various fields. (we don't remove softcode references)
		for d in self[:]:
			if d.flags & ObjectFlags.JUNK:
				continue
			if d.home == dbref:
				d.home = NOTHING
			if d.owner == dbref:
				d.owner = NOTHING
			if d.location == dbref:
				d.location = o.home

		o.destroyedTime = time.time()

	# base function for creating a blank object.
	def _newObject(self):

		o = DbObject()

		# get a #dbref for this object. If there are objects that have been fully recycled, use one. 
		# otherwise use a new dbref in the database.
		if (len(self.recycled)):
			dbref = self.recycled.pop()
			self[dbref] = o
		else:
			dbref = self.next
			self.append(o)
			self.next += 1

		o.dbref = dbref 
		
		return dbref 

	# object template functions for creating new objects, players, rooms, exits
	def newObject(self,player):

		dbref = self._newObject()
		o = self[dbref]

		# default is to be owned by the initiating player and in that player's inventory
		o.owner = player.dbref
		o.location = player.dbref
		player.contents.append(dbref)
		o.home = player.dbref 

		return dbref 

	def newRoom(self,player):

		dbref = self._newObject()
		o = self[dbref]

		o.flags |= ObjectFlags.ROOM 	# set the ROOM flag on this object.
		o.owner = player.dbref       	# player is the default owner.
		o.location = dbref 				# default drop to is what location is used for in rooms.
		o.home = dbref 
		
		return dbref


	def newPlayer(self,player):

		dbref = self._newObject()

		o = self[dbref]
		
		o.flags |= ObjectFlags.PLAYER 		# set the PLAYER flag on this object.
		o.owner = dbref       				# Players are owned by themselves.
		
		o.location = self.playerBase 		# Use the enactor location as the default location for the player
		o.home = self.playerBase 			# set to player base as initial home.
		
		return dbref

	def newExit(self,player):

		dbref = self._newObject()
		o = self[dbref]
		
		o.flags |= ObjectFlags.EXIT
		o.location = player.location 
		o.owner = player.dbref
		o.home = player.location

		return dbref 

	def validDbref(self,dbref):
		return dbref != None and dbref >= 0 and dbref < self.next

	def recycle(self): 

		recycled = []

		for dbref in self.junk:
			if time.time() - self[dbref].destroyedTime > _RECYCLE_WAIT:
				recycled.append(dbref)
				self.recycled.append(dbref)

		for dbref in recycled:
			self.junk.remove(dbref)










