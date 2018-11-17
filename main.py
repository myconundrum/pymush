from mushstate import mush
from commands import handleInput
import database


def main():

	mush.start()

	while mush.running:
		
		# do all internal mush state updates
		mush.update()

		# parse all commands from players
		cmds = mush.getCommands()
		for c in cmds:
			handleInput(c)


	
main()