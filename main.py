from mushstate import mush
from commands import handleInput
import database


def main():

	#mush.start()

	#while mush.running:
		
		# do all internal mush state updates
		#mush.update()

		# parse all commands from players
		#cmds = mush.getCommands()
		#for c in cmds:
		#	handleInput(c)


	db = database.Database()

	print (db)
	print (db[0])
	god = db[db.god]

	dbref = db.newObject(god)
	dbref = db.newObject(god)
	del db[2]

	print (db)
	print (db.junk)

	print (db[2].flags)

main()