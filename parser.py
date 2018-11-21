
import re
import math
from mushstate import mush
from database import ObjectFlags
from utils import * 



def dbrefify(term,enactor,obj):
	term = term.strip().upper()

	if (term == "" or term=="HERE"):
		return mush.db[enactor].location # assume no argument defaults to current location of enactor

	if (term == "ME"):
		return enactor

	# look in the contents of the current room
	for d in mush.db[mush.db[enactor].location].contents:
		if (aliasMatch(d,term)):
			return d 

	# look in inventory
	for d in mush.db[enactor].contents:
		if (aliasMatch(d,term)):
			return d

	if (term[0] == '#' and term[1:].isnumeric()):
		dbref = int(term[1:])		
		if mush.db[dbref].location == mush.db[enactor].location or mush.db[dbref].location == enactor or \
			mush.db[dbref].owner == enactor or mush.db[enactor].flags & ObjectFlags.WIZARD:
			return dbref if mush.db.validDbref(dbref) else None 

	return None



#
# For Mush functions
# A negative dbref (#-) is considered false
# The number 0 is considered false
# An empty string is considered false
# None string is considered false.
# anything else is True.
# 
def boolify(term):
	if (term == None):
		return False
	if (term[0:2] == '#-'): 
		return False
	if (len(term) == 0): 
		return False
	if (isnum(term)):
		return numify(term) != 0

	return True

def evalAttribute(dbref,attr,enactor):

	if attr not in mush.db[dbref]:
		return ""
	else:
		(val,line) = eval(mush.db[dbref][attr],"",enactor,dbref)

	return val

def isInt(string):
	try: 
		int(string)
		return True
	except ValueError:
		return False


def isFloat(string):
    try:
        float(string)
        return True
    except ValueError:
        return False

def isnum(term):

	return isInt(term) or isFloat(term)


def numify(term):

	if (isInt(term)):
		val = int(term)
	elif(isFloat(term)):
		val = float(term)
	else:
		val = 0

	return val

def nextTok(line):
	return None if line == None else line[1:]


def getTerms(line,enactor,obj):
	terms = []
	done = False
	while not done:

		(term,line) = eval(line,",)",enactor,obj)
		terms.append(term)
		if line == None or line[0] == ')':
			done = True
		 
		line = nextTok(line)

	return (terms,line)

def getOneTerm(line,enactor,obj):
	(term,line) = eval(line,")",enactor,obj)
	line = nextTok(line)
	return (term,line)
	

def fnAdd(line,enactor,obj):

	rval = 0
	(terms,line) = getTerms(line,enactor,obj)
	for t in terms:
		rval += numify(t)

	return (str(rval),line)

def fnAnd(line,enactor,obj):

	(terms,line) = getTerms(line,enactor,obj)
	for t in terms:
		if (boolify(t) == False):
			return ("0",line)

	return ("1",line)


def fnAlphaMax(line,enactor,obj):

	(words,line) = getTerms(line,enactor,obj)
	words.sort(reverse=True)
	return (words[0],line)

def fnAlphaMin(line,enactor,obj):
	(words,line) = getTerms(line,enactor,obj)
	words.sort()
	return (words[0],line)	


def fnAbs(line,enactor,obj):
	(term,line) = eval(line,")",enactor,obj)
	rval = abs(numify(term))
	line = nextTok(line)
	return (str(rval),line)


def fnAfter(line,enactor,obj):

	(baseStr,line) = eval(line,",",enactor,obj)
	line = nextTok(line)
	(testStr,line) = eval(line,")",enactor,obj)
	line = nextTok(line)
	l = baseStr.split(testStr,1)
	return (l[1] if len(l) > 1 else "",line)
	
def fnAcos(line,enactor,obj):
	(term,line) = eval(line,")",enactor,obj)
	rval = math.acos(numify(term))
	line = nextTok(line)
	return (str(rval),line)


	
def fnAsin(line,enactor,obj):
	(term,line) = eval(line,")",enactor,obj)
	rval = math.asin(numify(term))
	line = nextTok(line)
	return (str(rval),line)


	
def fnAtan(line,enactor,obj):
	(term,line) = eval(line,")",enactor,obj)
	rval = math.atan(numify(term))
	line = nextTok(line)
	return (str(rval),line)

def fnNotImplemented(line,enactor,obj):
	return("#-1 Function Not Implemented",line)

def fnAPoss(line,enactor,obj):

	rval = "its"

	(term,line) = getOneTerm(line,enactor,obj)
	dbref = dbrefify(term,enactor,obj)
	sex = evalAttribute(dbref,"SEX",enactor).upper()
	if (sex=="MALE" or sex == "M" or sex == "MAN"):
		rval = "his"
	elif(sex=="FEMALE" or sex =="F" or sex == "WOMAN" ):
		rval = "hers"
	elif(sex == "PLURAL"):
		rval = "theirs"

	return (rval,line)


def fnArt(line,enactor,obj):

	(term,line) = getOneTerm(line,enactor,obj)
	if (term != None) and term[0].upper() in "AEIOU":
		return ("an",line)

	return ("a",line)

# takes up to ten lists of numbers and averages. 
# lists are space delimited and there is a comma between each list
def fnAvg(line,enactor,obj):

	rval = 0
	count = 0
	(lists,line) = getTerms(line,enactor,obj)

	for l in lists:
		l=l.split(' ')
		for term in l: 
			count += 1
			rval += numify(term)

	return (str(round(rval/count,6)),line)



def fnBefore(line,enactor,obj):

	(baseStr,line) = eval(line,",",enactor,obj)
	line = nextTok(line)
	(testStr,line) = eval(line,")",enactor,obj)
	line = nextTok(line)
	l = baseStr.split(testStr,1)
	return (l[0] if len(l) > 1 else "",line)

def fnCapStr(line,enactor,obj):
	(s,line) = getOneTerm(line,enactor,obj)
	s = s.capitalize() if s != None else "" 
	return (s,line)

def fnCat(line,enactor,obj):
	(terms,line) = getTerms(line,enactor,obj)
	s = " ".join(terms)
	return (s,line)

def fnCeil(line,enactor,obj):
	(s,line) = getOneTerm(line,enactor,obj)
	return (str(math.ceil(numify(s))),line)



fnList = {
	
	'ADD'		: fnAdd,
	'ABS'		: fnAbs,
	'ACOS'		: fnAcos,
	'AFTER'		: fnAfter,
	'ALPHAMAX'	: fnAlphaMax,
	'ALPHAMIN'  : fnAlphaMin,
	'AND'		: fnAnd,
	'ANDFLAGS'	: fnNotImplemented,
	'ANSI'		: fnNotImplemented,
	'ANSIIF'	: fnNotImplemented,
	'APOSS'		: fnAPoss,
	'ART'		: fnArt,
	'ASIN'		: fnAsin,
	'ATAN'		: fnAtan,
	'ATRLOCK'	: fnNotImplemented,
	'AVG'		: fnAvg,
	'BEEP'		: fnNotImplemented,
	'BEFORE'	: fnBefore,
	'CAND'		: fnAnd,
	'CAN_SEE'	: fnNotImplemented,
	'CAPSTR'	: fnCapStr,
	'CAT'		: fnCat,
	'CEIL'		: fnCeil,





}

def testParse():

	tests = [
		"     abc def ghi",
		"add(1,2,3)dog house",
		"abs(add(-1,-5,-6))candy",
		"add(-1,-5,-6))candy",
		"after(as the world turns,world)",
		"dog was here[add(1,2)]",
		"[dog was here[add(1,2)]",
		"add(dog,1,2,3,4",
		"add(1,2",
		"hello world! [alphamin(zoo,black,orangutang,yes)]",
		"alphamax(dog,zoo,abacus,cat)",
		"1",
		"and(0,1)",
		"and(dog,-12,3,#12)",
		"and(dog,-13,3,#-12)",
		"aposs(me)",
		"aposs(#1)",
		"art(aardvark) aardvark",
		"art(doghouse) doghouse",
		"avg(1 2 3 4 5,6 4 3,2,1 0 0 0 3 4 5 6 7 8)",
		"before(as the world turns,world)",
		"can_see(me,here)",
		"capstr(hello, world!)",
		"cat(hello,world,you,crazy,place!)",
		"ceil(64.78)",
		"ceil(64.23)",
		]


	for s in tests:
		print(f"evaluating \'{s}\': {eval(s,'',1,1)[0]}")




def evalSubstitution(ch,enactor,obj):

	if (ch == 'N'):
		return mush.db[enactor].name
	elif (ch == 'R'):
		return '\n'
	elif (ch == 'B'):
		return ' '
	elif (ch == '%'):
		return '%'

	# BUGBUG: Need to add other substitutions
	return ''



def eval(line,stops,enactor,obj):

	rStr = ""


	if (line == None) :
		return ("",None)

	# find first line...
	line = line.strip()

	# look for first term...
	match = re.search(r'\W',line)
	
	if (match):
		# extract the term.
		i = match.start()
		term = line[0:i].upper()


		# if the term is the name of a function, call that function, with an argument of the rest of the string.
		if line[i]=='(' and term in fnList:
			(s,line) = fnList[term](line[i+1:],enactor,obj)
			rStr += s 
		else: 
			# Not a match, so simply add what we found so far to the results string and update the line.
			rStr += line[0:i]
			line = line[i:]

	# Now loop through the rest of the string until we reach our stopchars or a special char.
	pattern = re.compile(f"[{stops}\[%]")
	while line != None:
		match = pattern.search(line)
		if (not match): 
			# No more special characters until the end of the string. 
			rStr += line 
			line = None 
		else:
			i = match.start() 
			rStr += line[:i]
			# Check for substitution characters
			if line[i] == '%':
				rStr += evalSubstitution(line[i+1],enactor,obj)
				line = line[i+1:]
			# check for brackets and recurse if found.
			elif line[i] == '[':
				(s,line) = eval(line[i+1:],"]",enactor,obj)
				rStr += s
				line = nextTok(line)
			# we must have found one of the stop chars. exit.
			else:
				line = line[i:]
				return (rStr,line)


	return (rStr,None)















