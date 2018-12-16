from mushstate import mush
from commands import handleCommand
import time
import re
from tests import checkMush

def main():

	checkMush()
	mush.start()

	while mush.running:
		
		# do all internal mush state updates
		mush.update()

		# pull a command from the mush queue and evaluate it.
		if mush.commandReady():
			handleCommand(mush.getCommand())
		
		
		# don't peg the cpu.
		time.sleep(0.01)
main()