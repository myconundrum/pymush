

from enum import Flag, auto, Enum
import time

class ObjectFlags(Flag) :
	NOFLAG  		= 0
	JUNK    		= auto() 
	CONNECTED		= auto()
	WIZARD 			= auto()
	DARK			= auto()

class ObjectTypes(Enum) :
	OBJECT 	= auto()
	ROOM 	= auto()
	EXIT 	= auto()
	PLAYER 	= auto()

class AttributeFlags(Flag) :
	NOFLAG 	= 0


def dbGetObjectFlagsString(flags): 
	l = []
	for f in ObjectFlags:
		if (f & flags):
			l.append(f.name)
	return " ".join(l)

class AttributeDictionary(dict):

	def __init__(self):
		self.exData = {}
		super(AttributeDictionary,self).__init__()

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
		self.exData[f"_{key}_time"] = time.time()
		self.exData[f"_{key}_flags"] = AttributeFlags.NOFLAG

	def __delitem__(self,key):
		key = key.upper()
		super(AttributeDictionary,self).__delitem__(key)
		del self.exData[f"_{key}_time"]
		del self.exData[f"_{key}_flags"]


	def getEx(self,key):
		if key in self:
			return {'value': self[key],'time:' : self.exData[f"_{key}_time"],'flags' : self.exData[f"_{key}_flags"]}
		else: 
			return None

	def setFlags(self,key,flags):
		self[f"_{key}_flags"] = flags

	


class DbObject: 

	def __init__(self,dbref,otype):
		self.dbref = dbref					 	# db ref for this object
		self.flags = ObjectFlags.NOFLAG 		# global flags
		self.type  = otype 						# type
		
		self._name = ""							# name of this object
												# name's can be aliased (a la exits) by separating by ';'
												# only the name before the first semicolon will be displayed in lists. 
												# note that this is controlled by the property below
		self._name_aliases = []					# this contains the aliases


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
		
		
		self.name = "Nothing"
		
		self.attributes = AttributeDictionary()	# attributes dictionary
		self.attributes["DESCRIPTION"] = "You see nothing special."

	
	

	
	@property
	def name(self): 
		return self._name


	@name.setter
	def name(self,value):
		self._name_all = value
		self._name_aliases = value.split(';')
		self._name = self._name_aliases[0]

	# matches names and aliases
	def matchNameAndAliases(self,val): 
		val = val.upper()
		for s in self._name_aliases:
			if (s.upper() == val):
				return True
		return False

	# returns the aliases along with the actual name.
	def nameAndAliases(self):
		return ';'.join(self._name_aliases)




class Db: 

	def __init__(self):

		self.objects 			= []
		self.deleted 			= []
		self.version		 	= 1

		# cold start -- master room.
		dbref = len(self.objects)
		self.objects.append(DbObject(dbref,ObjectTypes.ROOM))
		self.objects[dbref].name = "Master Room"
		self.objects[dbref].location = dbref 
		self.objects[dbref].attributes["description"]= \
		"You are in the seed of a universe and all about you mists swirl with possibility and potential."


	def createObject(self,player,type=ObjectTypes.OBJECT):

		dbref = len(self.objects)
		self.objects.append(DbObject(dbref,type))

		if (self.objects[dbref].type == ObjectTypes.OBJECT):
			self.objects[dbref].location = player.location
			player.contents.append(dbref)
			self.objects[dbref].owner = player.dbref

		return dbref

	def createRoom(self,player):
		dbref = self.createObject(player,ObjectTypes.ROOM)
		self.objects[dbref].location = dbref # default drop to is what location is used for in rooms.
		self.objects[dbref].owner = player.dbref	
		return dbref


	def createPlayer(self,player):
		dbref = self.createObject(player,ObjectTypes.PLAYER)
		self.objects[self.objects[dbref].location].contents.append(dbref)
		self.objects[dbref].owner = dbref
		return dbref


	def createExit(self,player):
		return self.createObject(player,ObjectTypes.EXIT)


	def deleteObject(self,dbref):

		if (dbref > len(self.objects)) :
			printf(f"Db: No object with id {dbref} found.")
			return

		if (self.objects[dbref].flags & DbObjectFlags.JUNK) : 
			printf(f"Db: Object with id {dbref} already marked for deletion.")

		self.deleted.append(dbref)
		self.objects[dbref].flags |= DbObjectFlags.JUNK
		print(f"Db: Object {dbref} marked for deletion.")



