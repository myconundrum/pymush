



from enum import Flag, auto, Enum
import time

_DB_VERSION = 1.00

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
	SPECIAL         = auto()   		# Set on certain special objects -- undeletable.


class AttributeFlags(Flag) :
	NOFLAG 	= 0


class DbObject(dict) :

	def __init__(self):


		super(DbObject,self).__init__()


		self.dbref = dbref					 	# db ref for this object
		self.flags = ObjectFlags.NOFLAG 		# global flags
	

		self.location = 0						# contains a dbref. definition varies by object type. 
												# if player or object, is the the location room
												# if exit, points to the destination
												# if room points to drop-to.
		self.contents = []						# list of dbrefs contained in this object

		self.exits = [] 						# if this is a player or object, then points to HOME
												# if this is an exit, points to the source room
												# if this is a room, this is a list of exits

		self.owner = 0							# owner dbref of this object

		self.creationTime = time.time()			# object created...
		self.lastModified = time.time()			# object modified...


		self.attrEx  = {}						# Extended attribute information is stored here (owner, flags, etc)

		self.shortName = ""						# Name without aliases. 
		
		
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
		super(AttributeDictionary,self).__setitem__(key,value)

		self.exData[f"_{key}_owner"] = self.dbref
		self.exData[f"_{key}_flags"] = AttributeFlags.NOFLAG
		self.lastModified = time.time()
		if (key == "NAME"):
			self.shortName = value.split(';',1)[0]


	def __delitem__(self,key):
		key = key.upper()
		super(AttributeDictionary,self).__delitem__(key)
		del self.exData[f"_{key}_owner"]
		del self.exData[f"_{key}_flags"]
		self.lastModified = time.time()
		
		# always have a name and description attribute.
		if (key == "NAME"):
			self["NAME"] = "Nothing"
		if (key == "DESCRIPTION"):
			self["DESCRIPTION"] = "You see nothing special."



	def getEx(self,key):
		key = key.upper()
		if key in self:
			return {'value': self[key],'owner:' : self.exData[f"_{key}_owner"],'flags' : self.exData[f"_{key}_flags"]}
		else: 
			return None

	def setAttrOwner(self,key,dbref):
		key = key.upper()
		if key in self:
			self.exData[f"_{key}_owner",dbref]
		self.lastModified = time.time()

	def setAttrFlags(self,key,flags):
		key = key.upper()
		if key in self:
			self.exData[f"_{key}_owner",flags]
		self.lastModified = time.time()



class Db(list):

	
	def __init__(self):

		super(Db,self).__init__()

		self.version = _DB_VERSION  # used to validate pickle data.

		
		self.next = 0				# Next new dbref
		self.junk = []				# junk dbrefs, waiting to be recycled.
		self.recycled = []			# recycled dbrefs, ready to be reused. 


	# This is necessary because dict has a custom pickler. Without having this __new__ and __getnewargs__ 
	# the extended attributes of our dictionary are not unpickled.
	def __new__(cls, *args, **kw):
		f = super().__new__(cls, *args, **kw)
		f.__init__()
		return f

	def __getnewargs__(self):
		return ()

	def __delitem__(self,index):
		
	# base function for creating a blank object.
	def _newObject(self):

		# get a #dbref for this object. If there are objects that have been fully recycled, use one. 
		# otherwise use a new dbref in the database.
		if (len(self.recycled)):
			dbref = self.recycled.pop()
		else:
			dbref = self.next
			self.next += 1

		self[dbref] 	= DbObject()		 # blank object
		
		return dbref 

	# object template functions for creating new objects, players, rooms, exits
	def newObject(self,player):

		dbref = self._newObject()

		# default is to be owned by the initiating player and in that player's inventory
		self[dbref].owner = player.dbref
		self[dbref].location = player.dbref
		player.contents.append(dbref)

		return dbref 

	def newRoom(self,player):

		dbref = self._newObject()
		
		self.flags |= ObjectFlags.ROOM 	# set the ROOM flag on this object.
		self.owner = player.dbref       # player is the default owner.
		self[dbref].location = dbref 	# default drop to is what location is used for in rooms.
		
		return dbref


	def newPlayer(self,player):

		dbref = self._newObject()
		
		self.flags |= ObjectFlags.PLAYER 		# set the PLAYER flag on this object.
		self.owner = dbref       				# Players are owned by themselves.
		self[dbref].location = player.dbref 	# Use the enactor location as the default location for the player
		
		return dbref

	def createExit(self,player):

		dbref = self._newObject()
		self.flags |= ObjectFlags.EXIT
		self.location = player.location 
		self.owner = player.dbref

		return dbref 


	def recycleObjects(self):






