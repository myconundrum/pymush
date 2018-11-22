

import database
from database import ObjectFlags
from utils import *
import time
from mushstate import mush
from fnmatch import fnmatch

## Helper functions
def testLock(player,dbref):

	lock = evalAttribute(dbref,"LOCK",player.dbref)
	lockDbref = findDbref(player,lock)

	if (lock == "" or lockDbref == player.dbref or lockDbref in player.contents or player.flags & ObjectFlags.WIZARD):
		mush.msgDbref(player.dbref,evalAttribute(dbref,"SUCCESS",player.dbref))
		mush.msgLocation(player.location,evalAttribute(dbref,"OSUCCESS",player.dbref),player.dbref)
		return True

	mush.msgDbref(player.dbref,evalAttribute(dbref,"FAIL",player.dbref))
	mush.msgLocation(player.location,evalAttribute(dbref,"OFAIL",player.dbref),player.dbref)
	
	return False


def moveObject(dbref,dbrefTo):

	o = mush.db[dbref]
	to = mush.db[dbrefTo]
	fr = mush.db[o.location]

	if (mush.db[dbrefTo].location == dbref):
		mush.msgDbref(dbref,"You can't enter objects in your inventory.")
		return

	if (testLock(o,dbrefTo)):
		# show leave messages
		mush.msgDbref(o.dbref,evalAttribute(fr.dbref,"LEAVE",o.dbref))
		mush.msgLocation(fr.dbref,evalAttribute(fr.dbref,"OLEAVE",o.dbref),o.dbref)

		# remove from current location.
		fr.contents.remove(o.dbref)
		
		# add to new location
		to.contents.append(o.dbref)
		o.location = to.dbref

		# show enter messages.
		mush.msgDbref(o.dbref,evalAttribute(to.dbref,"ENTER",o.dbref))
		mush.msgLocation(to.dbref,evalAttribute(to.dbref,"OENTER",o.dbref),o.dbref)




def objectTypeString(dbref):
	o = mush.db[dbref]
	v = o.flags & (ObjectFlags.ROOM | ObjectFlags.EXIT | ObjectFlags.PLAYER)
	return v.name if v else "OBJECT"

def findDbref(player,args): 
	
	args = args.strip().upper()

	if (args == "" or args=="HERE"):
		return player.location # assume no argument defaults to current location

	if (args == "ME"):
		return player.dbref

	# look in the contents of the current room
	for d in mush.db[player.location].contents:
		if (aliasMatch(d,args)):
			return d 

	# look in inventory
	for d in player.contents:
		if (aliasMatch(d,args)):
			return d

	if (args[0] == '#' and args[1:].isnumeric()):
		dbref = int(args[1:])
		if mush.db[dbref].location == player.location or mush.db[dbref].location == player.dbref or \
			mush.db[dbref].owner == player.dbref or player.flags & ObjectFlags.WIZARD:
			return dbref if mush.db.validDbref(dbref) else None 

	return None

def evalAttribute(dbref,attr,enactor):
	
	if attr not in mush.db[dbref]:
		return ""

	s = mush.db[dbref][attr]
	s = s.replace("%N",mush.db[enactor].name)
	s = s.replace("%B"," ")
	s = s.replace("%R","\n\n")
	s = s.replace("%!",f"#{dbref}") # 	%! = dbref of the object holding the attribute
	s = s.replace("%#",f"#{enactor}") # %# = dbref of the enactor of this eval
	s = s.replace("%L",f"#{mush.db[enactor].location}") # %L = enactor's location

	# Need to add gender possessives -- %s, %o, %p, %a (based on gender attribute being set
	# need to add softcode specifics.

	return s


## Command List


def kill(player,args,ex) : 

	if not player.flags & ObjectFlags.WIZARD:
		mush.log(0,f"{player.name} (#{player.dbref}) tried to kill the server.")
		mush.msgDbref(player.dbref,"It is dangerous to meddle in the affairs of wizards.")
		return
	
	mush.msgAll(f"{player.name} killed the server. Goodbye.")
	mush.log(0,f"{player.name} (#{player.dbref}) killed the server.")
	mush.quit()

def quit(player,args,ex) :

	mush.msgDbref(player.dbref,"Logging out. Goodbye.")
	mush.msgLocation(player.location,f"{player.name} disconnected.")
	mush.log(1,f"{player.name} (#{player.dbref}) disconnected.")
	
	player.flags ^= ObjectFlags.CONNECTED
	player.flags ^= ObjectFlags.DARK
	
	mush.disconnectUser(player.dbref)


def say(player,args,ex) :
	args.strip(" \n")
	mush.msgLocation(player.location,f"{player.name} says \"{args}\"",player.dbref)
	mush.msgDbref(player.dbref,f"You say \"{args}\"")

def emote(player,args,ex):
	mush.msgLocation(player.location,f"{player.name} {args}")

def semiemote(player,args,ex):
	mush.msgLocation(player.location,f"{player.name}{args}")
	
def create(player,args,ex ) :
	
	dbref = mush.db.newObject(player)
	mush.db[dbref]["NAME"] = args
	mush.msgDbref(player.dbref,f"Object named {args} created with ref #{dbref}.")
	mush.log(2,f"{player.name}(#{player.dbref}) created object named {args} (#{dbref}).")
	
	return dbref


def doDig (player,name,eout,eback):


	# create room.
	dbref = mush.db.newRoom(player)
	mush.db[dbref]["NAME"] = name
	mush.msgDbref(player.dbref,f"Room named {name} created with ref #{dbref}.")
	mush.log(2,f"{player.name}(#{player.dbref}) dug room named {name} (#{dbref}).")


	if (eout != None):
		dbrefExit = mush.db.newExit(player)
		mush.db[dbrefExit]["NAME"]= eout
		mush.db[dbrefExit].location = dbref 
		mush.db[dbrefExit].home = player.location
		mush.db[player.location].contents.append(dbrefExit)
		mush.msgDbref(player.dbref,f"Exit named {eout} created with ref #{dbrefExit}.")
		mush.log(2,f"{player.name}(#{player.dbref}) dug exit named {eout} (#{dbrefExit}).")


	if (eback != None):
		dbrefExit = mush.db.newExit(player)
		mush.db[dbrefExit]["NAME"] = eback
		mush.db[dbrefExit].location = player.location
		mush.db[dbrefExit].home = dbref
		mush.db[dbref].contents.append(dbrefExit)
		mush.msgDbref(player.dbref,f"Exit named {eback} created with ref #{dbrefExit}.")
		mush.log(2,f"{player.name}(#{player.dbref}) dug exit named {eback} (#{dbrefExit}).")


	return dbref



def dig(player, args,ex) :
	
	name = None
	eout = None
	eback = None

	# unpack command string to name and exits if they exist
	l = args.split("=",1)
	name = l[0].strip()

	if (len(l) > 1):
		l2 = l[1].split(",",1)
		eout = l2[0].strip()
		if (len(l2) > 1):
			eback = l2[1].strip()

	doDig(player,name,eout,eback)


#
# BUGBUG No.
def delete(player,args,ex) :
	dbref = findDbref(player,args)
	if dbref != None and (player.dbref == mush.db[dbref].owner or player.flags & ObjectFlags.WIZARD):
		mush.msgDbref(player.dbref,f"You delete object {mush.db[dbref].name} (#{dbref})")
		if dbref == player.location:
			mush.msgDbref(player.dbref,f"You delete the room you are in! Sending you home!")
			moveObject(player.dbref,player.home)
		del mush.db[dbref]


	
def inventory(player,args,ex) : 

	mush.msgDbref(player.dbref,"You are carrying:")
	for dbref in player.contents:
		mush.msgDbref(player.dbref,f"{mush.db[dbref].name}")


def lookRoom(player,dbref,ex) : 

	o =mush.db[dbref]
	mush.msgDbref(player.dbref,f"[{o.name}]\n\n{o['DESCRIPTION']}")

	# filter contents into exits and contents both that are not set DARK
	contents = [mush.db[x].name for x in o.contents if not mush.db[x].flags & ObjectFlags.EXIT and not mush.db[x].flags & ObjectFlags.DARK]
	exits = [mush.db[x].name for x in o.contents if mush.db[x].flags & ObjectFlags.EXIT and not mush.db[x].flags & ObjectFlags.DARK]
	
	if len(contents):
		s = '\n'.join(contents)
		mush.msgDbref(player.dbref,f"\nYou see:\n{s}")
	if len(exits):
		s = '\n'.join(exits)
		mush.msgDbref(player.dbref,f"\nObvious exits:\n{s}")



def look(player,args,ex) :

	dbref = findDbref(player,args)

	if (dbref == player.location):
		lookRoom(player,dbref,None)
		return
	
	if (dbref == None):
		mush.msgDbref(player.dbref,f"You don't see anything named {args} here.")
		return

	o = mush.db[dbref]
	mush.msgDbref(player.dbref,o.name)
	mush.msgDbref(player.dbref,o["DESCRIPTION"])




def attrset(player,args,attr) :
	
	args = args.split('=',1)
	
	if (len(args)<2):
		mush.msgDbref(player.dbref,"huh?")
		return

	dbref = findDbref(player,args[0])

	if (dbref == None):
		mush.msgDbref(player.dbref,f"You don't see anything named {args[0]} here.")
		return

	if mush.db[dbref].owner != player.dbref and not player.flags & ObjectFlags.WIZARD:
		mush.msgDbref(player.dbref,f"You don't own that.")
		return

	mush.db[dbref][attr] = args[1]
	mush.db[dbref].setAttrOwner(attr,player.dbref)
	mush.msgDbref(player.dbref,"Set.")


def drop (player,args,ex) :

	dbref = findDbref(player,args)
	if dbref not in player.contents:
		mush.msgDbref(player.dbref,"You don't have that.")
		return

	# drop the object
	moveObject(dbref,player.location)

	mush.msgDbref(player.dbref,evalAttribute(dbref,"DROP",player.dbref))
	mush.msgLocation(player.location,evalAttribute(dbref,"ODROP",player.dbref),player.dbref)


def take(player,args,ex) :

	dbref = findDbref(player,args)
	if dbref not in mush.db[player.location].contents:
		mush.msgDbref(player.dbref,"You don't see that here.")
		return

	if (testLock(player,dbref)):
		moveObject(dbref,player.dbref)

def setfn(player,args,ex):

	l = args.split('=',1)
	if (len(l) == 1):
		mush.msgDbref(player.dbref,"Huh?")
		return

	if (l[0].find('/') != -1):
		# BUGBUG implement set attrflag here...
		return

	if (l[1].find(':') != -1):
		#BUGBUG implmeent set attribute here...
		return

	# set flag value.
	dbref = findDbref(player,l[0])
	if (dbref == None):
		mush.msgDbref(player.dbref,f"Could not find an object with id {l[0]}.")
		return

	# find the flag name to set, and see if we are setting or clearing.
	l[1] = l[1].strip().upper()
	clear = l[1].strip()[0] == '!'
	if (clear):
		l[1] = l[1][1:]

	for flag in ObjectFlags:
		if flag.name == l[1]:
			if (clear): 
				mush.db[dbref].flags = mush.db[dbref].flags & ~flag
				mush.msgDbref(player.dbref,f"Flag {flag.name} reset on {mush.db[dbref].name} (#{dbref})")
			else: 
				mush.db[dbref].flags |= flag
				mush.msgDbref(player.dbref,f"Flag {flag.name} set on {mush.db[dbref].name} (#{dbref})")
			

def examineAttr(player,dbref,pattern):

	pattern = pattern.upper()
	matches = [x for x in mush.db[dbref] if fnmatch(x,pattern)]

	if (len(matches)):
		mush.msgDbref(player.dbref,"\n".join([f"{x} [#{mush.db[dbref].getAttrOwner(x)}]: {mush.db[dbref][x]}" for x in matches]))
	else:
		mush.msgDbref(player.dbref,"No matching attributes.")




def examine(player,args,ex) :

	# look to see if this is an attr examine command
	args = args.split('/',1)

	dbref = findDbref(player,args[0])
	if (dbref == None):
		mush.msgDbref(player.dbref,f"Could not find an object with id {args[0]}.")
		return

	if (len(args) > 1):
		examineAttr(player,dbref,args[1])
		return

	o = mush.db[dbref]
	mush.msgDbref(player.dbref,f"{o['NAME']}(#{dbref})")
	mush.msgDbref(player.dbref,f"Type: {objectTypeString(dbref)} Flags: {' '.join([x.name for x in ObjectFlags if o.flags & x])}")
	mush.msgDbref(player.dbref,f"Owner: {mush.db[o.owner].name}(#{mush.db[o.owner].dbref}) Location: {mush.db[o.location].name}(#{mush.db[o.location].dbref})")
	
	if not o.flags & (ObjectFlags.ROOM):
		mush.msgDbref(player.dbref,f"Home: {mush.db[o.home].name}(#{mush.db[o.home].dbref})")
	mush.msgDbref(player.dbref,f"Created: {time.ctime(o.creationTime)}")
	mush.msgDbref(player.dbref,f"Modified: {time.ctime(o.lastModified)}")
	if (o.flags & ObjectFlags.JUNK):
		mush.msgDbref(player.dbref,f"Destroyed: {time.ctime(o.destroyedTime)}")

	if ex == "ALL":
		mush.msgDbref(player.dbref,"\n".join([f"{x} [#{o.getAttrOwner(x)}]: {o[x]}" for x in o]))

	# filter into content and exits and show. Right now all (even DARK) are shown. Should check
	# for see_all or similar.
	contents = [f"{mush.db[x]['NAME']} (#{mush.db[x].dbref})" for x in o.contents if not mush.db[x].flags & ObjectFlags.EXIT]
	exits = [f"{mush.db[x]['NAME']} (#{mush.db[x].dbref})" for x in o.contents if mush.db[x].flags & ObjectFlags.EXIT]
	
	if len(contents):
		s = '\n'.join(contents)
		mush.msgDbref(player.dbref,f"\nContents:\n{s}")
	if len(exits):
		s = '\n'.join(exits)
		mush.msgDbref(player.dbref,f"\nExits:\n{s}")



def saveDb(player,args,ex):

	if (player.flags & ObjectFlags.WIZARD):
		mush.save()
		mush.msgDbref(player.dbref,f"database saved.")
		mush.log(0,f"{player.name} (#{player.dbref}) kicked off a database save.")

	else : 
		mush.msgDbref(player.dbref,"It is not wise to meddle in the affairs of wizards.")
	

def loadDb(player,args,ex):

	if (player.flags & ObjectFlags.WIZARD):
		mush.load()
		mush.log(0,f"{player.name} (#{player.dbref}) kicked off a database load.")
		mush.msgDbref(player.dbref,f"database loaded.")
		mush.msgAll(f"{player.name} kicked off a reload of the database.");
	else : 
		mush.msgDbref(player.dbref,"It is not wise to meddle in the affairs of wizards.")
	
def think(player,args,ex):
	mush.msgDbref(player.dbref,args)




def enter(player,args,ex): 

	dbref = findDbref(player,args)
	if (dbref == None):
		mush.msgDbref(player.dbref,f"Could not find an object with id {args}.")
		return

	o = mush.db[dbref]

	if (o.flags & ObjectFlags.ENTER_OK):
		moveObject(player.dbref,dbref)
		look(player,"",None)
	else:
		mush.msgDbref(player.dbref,"You can't enter that.")

	
def leave(player,args,ex):

	if (mush.db[player.location].flags & ObjectFlags.ROOM):
		mush.msgDbref(player.dbref,"Use an exit to leave this room.")
		return

	moveObject(player.dbref,mush.db[player.location].location)


def link(player,args,ex):

	args=args.upper()
	args=args.split('=',1)

	if (len(args) != 2):
		mush.msgDbref(player.dbref,"huh? Usage: @LINK <obj>=<destination>.")
		return

	obj = findDbref(player,args[0])
	to = findDbref(player,args[1])

	if (player.flags & ObjectFlags.WIZARD or \
		(player.dbref == mush.db[obj].owner and (player.dbref == mush.db[to].owner or mush.db[to].flags & LINK_OK))):
		if (mush.db[obj].flags & (ObjectFlags.ROOM | ObjectFlags.EXIT)):
			mush.db[obj].location = to 
		else:
			mush.db[obj].home = to 

		mush.msgDbref(player.dbref,"Linked.")
	else:
		mush.msgDbref(plsyer.dbref,"You don't have permission to do that.")

def home(player,args,ex):
	mush.msgDbref(player.dbref,"Going home...")
	moveObject(player.dbref,player.home)
	look(player,"","")


def teleport(player,args,ex):

	args=args.upper()
	args=args.split('=',1)

	if (len(args)>1):
		to = findDbref(player,args[1])
		obj = findDbref(player,args[0])
	else:
		to = findDbref(player,args[0])
		obj = player.dbref 

	# Need to be a WIZARD or own an object in order to telpeort to it.
	if player.flags & ObjectFlags.WIZARD or mush.db[to].owner == player.dbref:
		moveObject(obj,to)
		if (mush.db[obj].flags & ObjectFlags.PLAYER):
			look(mush.db[obj],"","")
		else: 
			mush.msgDbref(player.dbref,"Teleported.")


## commands end





def tryExits(player,exit):

	exits = [x for x in mush.db[player.location].contents if mush.db[x].flags & ObjectFlags.EXIT]

	for d in exits:
		if (aliasMatch(d,exit) and testLock(player,d)):
			moveObject(player.dbref,mush.db[d].location)
			look(player,"","")
			return True

	return False

def handleConnectingPlayer(pid,cmd,args):

	if (cmd == "CONNECT"):
		
		l = args.split(" ",1)

		if not mush.userExists(l[0]):
			mush.msgPid(pid,"Bad username or password. Try again.")
			return 

		if (len(l) == 1):
			mush.msgPid(pid,"No password. Try again.")
			return 

		if not mush.connectUser(l[0],pid,l[1]):
			mush.msgPid(pid,"Bad username or password. Try again.")
			return 


		p = mush.db[mush.pidToDbref[pid]]
		p.flags |= ObjectFlags.CONNECTED
		p.flags ^= ObjectFlags.DARK
		mush.msgLocation(p.location,f"{p.name} connected.")
		mush.log(1,f"{p.name} (#{p.dbref}) connected.")
		look(p,"","")

	if (cmd == "CREATE"):
		
		l = args.split(" ",1)

		if mush.userExists(l[0]):
			mush.msgPid(pid,"That name already exists. Choose another.")
			return 

		if (len(l)==1):
			mush.msgPid(pid,"No password. Try again.")
			return 
		
		# create a new player object in the game
		dbref = mush.db.newPlayer(None)
		mush.db[dbref]["NAME"] = l[0]
		mush.db[dbref].flags |= ObjectFlags.CONNECTED
		mush.db[dbref].location = mush.db.playerBase
		mush.db[mush.db.playerBase].contents.append(dbref)

		
		mush.newUser(dbref,pid,l[1])
		mush.msgLocation(mush.db[dbref].location,f"Character named {mush.db[dbref].name} created.")
		look(mush.db[dbref],"","")
		mush.log(1,f"New user created named {mush.db[dbref].name} with dbref #{dbref}")
		

def handleInput(data):

	(pid,cmd,args) = data

	# catch empty input.
	if (len(cmd)==0):
		return

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
		
	# upper case the command to do proper matching
	cmd = cmd.upper()

	if (mush.pidToDbref[pid] == -1):
		handleConnectingPlayer(pid,cmd,args)
		return

	# see if it was an exit command.
	if (tryExits(mush.db[mush.pidToDbref[pid]],cmd)):
		return

	if (gCommands.get(cmd)):
		gCommands[cmd]["fn"](mush.db[mush.pidToDbref[pid]],args,gCommands[cmd]["ex"])
		return


gCommands = {

	"QUIT" 			: {"fn" : quit, "ex" : None},
	"KILL"			: {"fn" : kill, "ex" : None},
	"SAY"  			: {"fn" : say, "ex" : None},
	"\""			: {"fn" : say, "ex" : None},
	"EMOTE"			: {"fn" : emote, "ex" : None},
	":"				: {"fn" : emote, "ex" : None},
	"SEMIEMOTE"		: {"fn" : semiemote, "ex" : None},
	";"				: {"fn" : semiemote, "ex" : None},
	"@CREATE"		: {"fn" : create, "ex" : None},
	"@CR"			: {"fn" : create, "ex" : None},
	"@DIG"			: {"fn" : dig, "ex" : None},
	"@DESCRIBE"		: {"fn" : attrset, "ex" : "DESCRIPTION"},
	"@DESC"			: {"fn" : attrset, "ex" : "DESCRIPTION"},
	"@SUCCESS"		: {"fn" : attrset, "ex" : "SUCCESS"},
	"@SUCC"			: {"fn" : attrset, "ex" : "SUCCESS"},
	"@OSUCCESS"		: {"fn" : attrset, "ex" : "OSUCCESS"},
	"@OSUCC"		: {"fn" : attrset, "ex" : "OSUCCESS"},
	"@DROP"			: {"fn" : attrset, "ex" : "DROP"},
	"@ODROP"		: {"fn" : attrset, "ex" : "ODROP"},
	"@ENTER"		: {"fn" : attrset, "ex" : "ENTER"},
	"@OENTER"		: {"fn" : attrset, "ex" : "OENTER"},
	"@LEAVE"		: {"fn" : attrset, "ex" : "LEAVE"},
	"@OLEAVE"		: {"fn" : attrset, "ex" : "OLEAVE"},
	"@NAME"			: {"fn" : attrset, "ex" : "NAME"},
	"@FAIL"			: {"fn" : attrset, "ex" : "FAIL"},
	"@OFAIL"		: {"fn" : attrset, "ex" : "OFAIL"},

	"@LINK"			: {"fn" : link, "ex": None},
	"HOME"			: {"fn" : home, "ex": None},

## LOCKS
	"@LOCK"			: {"fn" : attrset, "ex" : "LOCK"},
	"@ELOCK"		: {"fn" : attrset, "ex" : "ELOCK"},
	"@LOCK/ENTER"	: {"fn" : attrset, "ex" : "ELOCK"},
	"@LOCK/TEL"		: {"fn" : attrset, "ex" : "TLOCK"},
	"@LOCK/TELEPORT": {"fn" : attrset, "ex" : "TLOCK"},
	"@LOCK/USE"		: {"fn" : attrset, "ex" : "ULOCK"},


	"@TELEPORT"		: {"fn" : teleport, "ex" : None},
	"@TEL"			: {"fn" : teleport, "ex" : None},

	"@SET"			: {"fn" : setfn, "ex" : None},
	"@DESTROY"		: {"fn" : delete, "ex" : None},
	
	"E"				: {"fn" : examine, "ex" : "ALL"},
	"EX"			: {"fn" : examine, "ex" : "ALL"},
	"EXAMINE"		: {"fn" : examine, "ex" : "ALL"},
	"BRIEF"			: {"fn" : examine, "ex" : None},
	"BR"			: {"fn" : examine, "ex" : None},
	"B"				: {"fn" : examine, "ex" : None},
	
	"LOOK"			: {"fn" : look, "ex" : None},
	"INVENTORY"		: {"fn" : inventory, "ex" : None},
	"I"				: {"fn" : inventory, "ex" : None},
	"DROP"			: {"fn" : drop, "ex" : None},
	"TAKE"			: {"fn" : take, "ex" : None},
	"GET" 			: {"fn" : take, "ex" : None},
	"SAVE" 			: {"fn" : saveDb, "ex" : None},
	"LOAD" 			: {"fn" : loadDb, "ex" : None},
	"THINK"			: {"fn" : think, "ex" : None},
	"ENTER"			: {"fn" : enter, "ex" : None},
	"LEAVE"			: {"fn" : leave, "ex" : None}
}

