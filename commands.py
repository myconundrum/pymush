


import odb
import os.path
import time
from mushstate import mush

def findDbref(player,args): 
	args = args.strip().upper()
	loc = player.location

	if (args == "" or args=="HERE"):
		return loc # assume no argument defaults to current location

	if (args == "ME"):
		return player.dbref

	# look in the contents of the current room
	o = mush.db.objects[loc]
	for d in o.contents:
		t = mush.db.objects[d]
		if (t.matchNameAndAliases(args)):
			return t.dbref 

	# look in inventory
	for d in player.contents:
		t = mush.db.objects[d]
		if (t.matchNameAndAliases(args)):
			return t.dbref

	if (args[0] == '#'):
		return int(args[1:])

	return None



def evalAttribute(dbref,attr,enactor):
	if attr not in mush.db.objects[dbref].attributes:
		return ""

	s = mush.db.objects[dbref].attributes[attr]
	s = s.replace("%N",mush.db.objects[enactor].name)
	s = s.replace("%B"," ")
	s = s.replace("%R","\n\n")
	s = s.replace("%!",f"#{dbref}") # 	%! = dbref of the object holding the attribute
	s = s.replace("%#",f"#{enactor}") # %# = dbref of the enactor of this eval
	s = s.replace("%L",f"#{mush.db.objects[enactor].location}") # %L = enactor's location

	# Need to add gender possessives -- %s, %o, %p, %a (based on gender attribute being set
	# need to add softcode specifics.

	return s


def kill(player,args,ex) : 
	mush.msgAll(f"{player.name} killed the server. Goodbye.")
	mush.log(0,f"{player.name} (#{player.dbref}) killed the server.")
	mush.quit()

def quit(player,args,ex) :
	mush.msgDbref(player.dbref,"Logging out. Goodbye.")
	mush.msgLocation(player.location,f"{player.name} disconnected.")
	mush.log(1,f"{player.name} (#{player.dbref}) disconnected.")
	player.flags ^= odb.ObjectFlags.CONNECTED
	player.flags ^= odb.ObjectFlags.DARK
	mush.disconnectUser(player.dbref)


def say(player,args,ex) :
	mush.msgLocation(player.location,f"{player.name} says \"{args}.\"",player.dbref)
	mush.msgDbref(player.dbref,f"You say \"{args}.\"")

def emote(player,args,ex):
	mush.msgLocation(player.location,f"{player.name} {args}")

def semiemote(player,args,ex):
	mush.msgLocation(player.location,f"{player.name}{args}")
	
def create(player,args,ex ) :
	dbref = mush.db.createObject(player)
	mush.db.objects[dbref].name = args
	mush.msgDbref(player.dbref,f"Object named {args} created with ref #{dbref}.")
	mush.log(2,f"{player.name}(#{player.dbref}) created object named {args} (#{dbref}).")

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

	dbref = mush.db.createRoom(player)
	mush.db.objects[dbref].name = name
	mush.msgDbref(dbref,f"Room named {name} created with ref #{dbref}.")
	mush.log(2,f"{player.name}(#{player.dbref}) dug room named {name} (#{dbref}).")


	if (eout != None):
		dbrefExit = mush.db.createExit(player)
		mush.db.objects[dbrefExit].name = eout
		mush.db.objects[dbrefExit].location = dbref 
		mush.db.objects[player.location].contents.append(dbrefExit)
		mush.msgDbref(player.dbref,f"Exit named {eout} created with ref #{dbrefExit}.")
		mush.log(2,f"{player.name}(#{player.dbref}) dug exit named {eout} (#{dbrefExit}).")


	if (eback != None):
		dbrefExit = mush.db.createExit(player)
		mush.db.objects[dbrefExit].name = eback
		mush.db.objects[dbrefExit].location = player.location
		mush.db.objects[dbref].contents.append(dbrefExit)
		mush.msgDbref(player.dbref,f"Exit named {eback} created with ref #{dbrefExit}.")
		mush.log(2,f"{player.name}(#{player.dbref}) dug exit named {eback} (#{dbrefExit}).")

#
# BUGBUG No.
def delete(player,args,ex) :
	db.deleteObject(int(args))




def inventory(player,args,ex) : 

	mush.msgDbref(player.dbref,"You are carrying:")
	for dbref in player.contents:
		mush.msgDbref(player.dbref,f"{mush.db.objects[dbref].name}")


def lookRoom(player,dbref,ex) : 
	o =mush.db.objects[dbref]
	mush.msgDbref(player.dbref,f"{o.name}\n{o.attributes['DESCRIPTION']}")

	l = [d for d in o.contents if (mush.db.objects[d].type != odb.ObjectTypes.EXIT and not mush.db.objects[d].flags & odb.ObjectFlags.DARK)]
	if (len(l)):
		mush.msgDbref(player.dbref,"\nYou see: ")
		for d in l:
			mush.msgDbref(player.dbref,mush.db.objects[d].name)

	l = [d for d in o.contents if (mush.db.objects[d].type == odb.ObjectTypes.EXIT and not mush.db.objects[d].flags & odb.ObjectFlags.DARK)]
	if (len(l)):
		mush.msgDbref(player.dbref,"\nObvious exits: ")
		for d in l:
			mush.msgDbref(player.dbref,mush.db.objects[d].name)


def look(player,args,ex) :

	dbref = findDbref(player,args)

	if (dbref == player.location):
		lookRoom(player,dbref,None)
		return
	
	if (dbref == None):
		mush.msgDbref(player.dbref,f"You don't see anything named {args} here.")
		return

	o = db.objects[dbref]
	mush.msgDbref(player.dbref,o.name)
	if ("DESCRIPTION" in o.attributes):
		mush.msgDbref(player.dbref,o.attributes["DESCRIPTION"])


def attrset(player,args,attr) :
	
	args = args.split('=',1)
	dbref = findDbref(player,args[0])

	if (dbref == None):
		mush.msgDbref(player.dbref,f"You don't see anything named {args} here.")
		return

	if mush.db.objects[dbref].owner != player.dbref and not player.flags & odb.ObjectFlags.WIZARD:
		mush.msgDbref(player.dbref,f"You don't own that.")
		return

	if (attr == "NAME") : 
		mush.db.objects[dbref].name = args[1]
	else : 	
		mush.db.objects[dbref].attributes[attr] = args[1]

	mush.msgDbref(player.dbref,"Set.")


def drop (player,args,ex) :

	dbref = findDbref(player,args)
	if dbref not in player.contents:
		mush.msgDbref(player.dbref,"You don't have that.")
		return

	# drop the object
	player.contents.remove(dbref)
	mush.db.objects[player.location].contents.append(dbref)
	mush.msgDbref(player.dbref,evalAttribute(dbref,"DROP",player.dbref))
	mush.msgLocation(player.location,evalAttribute(dbref,"ODROP",player.dbref),player.dbref)

def take(player,args,ex) :

	dbref = findDbref(player,args)
	if dbref not in mush.db.objects[player.location].contents:
		mush.msgDbref(player.dbref,"You don't see that here.")
		return

	if (testLock(player,dbref)):
		player.contents.append(dbref)
		mush.db.objects[player.location].contents.remove(dbref)

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

	for flag in odb.ObjectFlags:
		if flag.name == l[1]:
			if (clear): 
				mush.db.objects[dbref].flags = mush.db.objects[dbref].flags & ~flag
				mush.msgDbref(player.dbref,f"Flag {flag.name} reset on {mush.db.objects[dbref].name} (#{dbref})")
			else: 
				mush.db.objects[dbref].flags |= flag
				mush.msgDbref(player.dbref,f"Flag {flag.name} set on {mush.db.objects[dbref].name} (#{dbref})")
			

def examine(player,args,ex) :

	dbref = findDbref(player,args)
	if (dbref == None):
		mush.msgDbref(player.dbref,f"Could not find an object with id {dbref}.")
		return

	o = mush.db.objects[dbref]
	mush.msgDbref(player.dbref,f"{o.nameAndAliases()}(#{dbref})")
	mush.msgDbref(player.dbref,f"Type: {o.type.name} Flags: {odb.dbGetObjectFlagsString(o.flags)}")
	mush.msgDbref(player.dbref,f"Owner: {mush.db.objects[o.owner].name}(#{mush.db.objects[o.owner].dbref}) Location: {mush.db.objects[o.location].name}(#{mush.db.objects[o.location].dbref})")
	mush.msgDbref(player.dbref,f"Created: {time.ctime(o.creationTime)}")
	for s in o.attributes:
		mush.msgDbref(player.dbref,f"{s}: {o.attributes[s]}")


def saveDb(player,args,ex):
	mush.save(args)
	mush.msgDbref(player.dbref,f"database saved as {args}")
	

def loadDb(player,args,ex):
	mush.load(args)
	mush.msgDbref(player.dbref,f"database loaded from {args}")




## commands end

def testLock(player,dbref):

	lock = evalAttribute(dbref,"LOCK",player.dbref)

	
	lockDbref = findDbref(player,lock)

	if (lock == "" or lockDbref == player.dbref or lockDbref in player.contents):
		mush.msgDbref(player.dbref,evalAttribute(dbref,"SUCCESS",player.dbref))
		mush.msgLocation(player.location,evalAttribute(dbref,"OSUCCESS",player.dbref),player.dbref)
		return True

	mush.msgDbref(player.dbref,evalAttribute(dbref,"FAIL",player.dbref))
	mush.msgLocation(player.location,evalAttribute(dbref,"OFAIL",player.dbref),player.dbref)
	
	return False


def tryExits(player,exit):

	l = [d for d in mush.db.objects[player.location].contents if (mush.db.objects[d].type == odb.ObjectTypes.EXIT)]
	for d in l:
		if (mush.db.objects[d].matchNameAndAliases(exit) and testLock(player,d)):
			player.location = mush.db.objects[d].location
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


		p = mush.db.objects[mush.pidToDbref[pid]]
		p.flags |= odb.ObjectFlags.CONNECTED
		p.flags ^= odb.ObjectFlags.DARK
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
		dbref = mush.db.createPlayer(None)
		mush.db.objects[dbref].name = l[0]
		mush.db.objects[dbref].flags |= odb.ObjectFlags.CONNECTED
		
		mush.newUser(dbref,pid,l[1])
		mush.msgLocation(mush.db.objects[dbref].location,f"Character named {mush.db.objects[dbref].name} created.")
		look(mush.db.objects[dbref],"","")
		mush.log(1,f"New user created named {mush.db.objects[dbref].name} with dbref #{dbref}")
		
		


def handleInput(cmd):
	
	(pid,cmd,args) = cmd

	# special case some commands that don't end in a whitespace.
	if (cmd[0] == ':'): 
		args = f"{cmd[1:]} {args}"
		cmd = ':'
	elif (cmd[0] == ';'):
		args = f"{cmd[1:]} {args}"
		cmd = ';'

	# upper case the command to do proper matching
	cmd = cmd.upper()

	if (mush.pidToDbref[pid] == -1):
		handleConnectingPlayer(pid,cmd,args)
		return

	# see if it was an exit command.
	if (tryExits(mush.db.objects[mush.pidToDbref[pid]],cmd)):
		return

	if (gCommands.get(cmd)):
		gCommands[cmd]["fn"](mush.db.objects[mush.pidToDbref[pid]],args,gCommands[cmd]["ex"])
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
	"@NAME"			: {"fn" : attrset, "ex" : "NAME"},
	"@LOCK"			: {"fn" : attrset, "ex" : "LOCK"},
	"@FAIL"			: {"fn" : attrset, "ex" : "FAIL"},
	"@OFAIL"		: {"fn" : attrset, "ex" : "OFAIL"},
	"@SET"			: {"fn" : setfn, "ex" : None},
	"DELETE"		: {"fn" : delete, "ex" : None},
	"EX"			: {"fn" : examine, "ex" : None},
	"EXAMINE"		: {"fn" : examine, "ex" : None},
	"LOOK"			: {"fn" : look, "ex" : None},
	"INVENTORY"		: {"fn" : inventory, "ex" : None},
	"I"				: {"fn" : inventory, "ex" : None},
	"DROP"			: {"fn" : drop, "ex" : None},
	"TAKE"			: {"fn" : take, "ex" : None},
	"GET" 			: {"fn" : take, "ex" : None},
	"SAVE" 			: {"fn" : saveDb, "ex" : None},
	"LOAD" 			: {"fn" : loadDb, "ex" : None},
}

