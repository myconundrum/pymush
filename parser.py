
import re
##

# (1) we are looking for a command at the beginning of a string (evaluation on)
# (2) Scan until we find a special character (space, paren, etc)
# (3) Match found characters to decide if this is a function. If function, snarf argumetns and then evaluate
# (4) Turn off evaluation (evaluation off)
# (5) If find [, start parser recursion on that string]
##


def fnAdd(line):

	done = False
	rval = 0 
	while not done:
		(term,line) = parse(line,",)")
		rval += int(term) if term.isnumeric() else 0
		if len(line) == 0 or line[0] == ')':
			done = True
		else:
		 	line = line[1:]

	if (len(line)):
		line = line[1:]
	
	return (str(rval),line)





fnList = {
	
	'ADD': fnAdd,
}

def testParse():

	tests = [
		"     abc def ghi",
		"add(1,2,3)dog house",
		"dog was here[add(1,2)]",
		"[dog was here[add(1,2)]",
		"add(dog,1,2,3,4",
		"1"
		]


	for s in tests:
		print(f"evaluating \'{s}\': {parse(s)[0]}")




def parse(line,stopchars=""):

	# start with empty result string.
	rStr = ""

	# strip whitespace from the left side of the line.
	line = line.lstrip()

	# get the first "term" (substring until first "special char")
	match = re.search(r'\W',line)

	if (match):
		i = match.start()
		term = line[0:i].upper()


		# if the term is the name of a function, call that function, with an argument of the rest of the string.
		if line[i]=='(' and term in fnList:
			(s,line) = fnList[term](line[i+1:])
			rStr += s 
			i = 0
		else: 
			rStr += line[0:i]
	else:
		i = 0


	line = line[i:]
	i = 0

	# No longer actively evaluating for functions. Just add string to the result. 
	# stop if we find the end chars, and if we find a bracket, recurse into parsing.
	while (i < len(line) and line[i] not in stopchars):

		if (line[i] == '['):
			(s,line) = parse(line[i+1:],"]")
			rStr += s
			i = 0		
		else: 
			rStr += line[i]
		i+= 1

	# return the result and the rest of the line.
	return (rStr,line)


















