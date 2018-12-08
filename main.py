from mushstate import mush
from commands import handleInput
import time
import re
import parser
from tests import testParse



def init():

	mush.start()
	
	testParse()


def main():


	init()
	return

	while mush.running:
		
		# do all internal mush state updates
		mush.update()

		# parse all commands from players
		cmds = mush.getCommands()
		for c in cmds:
			handleInput(c)
		
		# don't peg the cpu.
		time.sleep(0.01)

	
main()