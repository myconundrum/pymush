
from mushstate import mush
from database import ObjectFlags

def message(dbref,msg):

	o = mush.db[dbref]
	
	# send actual message to the console of a connected player.
	if (o.flags & ObjectFlags.CONNECTED): 
		mush.server.send_message(mush.dbrefToPid[dbref],msg)

	# check to see if there is a LISTEN attribute that matches this.
	if "LISTEN" in o and (fnmatch.fnmatch(msg,o["LISTEN"])):
		print (f"Matched the LISTEN attribute of {o.name}")
		for action in ("" if not "AHEAR" in o else o["AHEAR"]).split(";"):
			mush.commandQueue.put(action)

	# this is a room. send the message to the contents of the room.
	if o.flags & ObjectFlags.ROOM:
		for dbref in o.contents:
			message(dbref,msg)












