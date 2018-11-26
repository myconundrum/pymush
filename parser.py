
import re
import math
import time
from mushstate import mush
from database import ObjectFlags
from utils import * 
import commands
import random
import fnmatch



gRegisters = []

def clearRegs():
	global gRegisters
	gRegisters = []
	for x in range(10): 
		gRegisters.append(0) 


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

def getObjAttr(term):

	sep = term.find('/')
	if (sep == -1):
		return (term,None)
	return (term[0:sep],term[sep+1:].upper())


def getTerms(line,enactor,obj):
	terms = []
	done = False
	while not done:

		(term,line) = eval(line,",)",enactor,obj)
		if term != "":
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


def fnCenter(line,enactor,obj):
	(terms,line) = getTerms(line,enactor,obj)
	if (len(terms) < 2 or len(terms) > 3):
		return ("#-1 Function expects 2 or 3 arguments.",line)
	width = numify(terms[1])
	pad = " " if len(terms) < 3 else terms[2]

	return (terms[0].center(width,pad),line)


def fnComp(line,enactor,obj):
	(terms,line) = getTerms(line,enactor,obj)
	if (len(terms) != 2):
		return ("#-1 Function expects 2 arguments.",line)

	val = 0
	if (terms[0] < terms[1]): 
		val = -1
	elif (terms[0] > terms[1]):
		val = 1

	return (str(val),line)


def fnClone(line,enactor,obj):

	(term,line) = getOneTerm(line,enactor,obj)
	dbref = dbrefify(term,enactor,obj)
	o = mush.db[dbref]
	if (o.flags & (ObjectFlags.ROOM | ObjectFlags.PLAYER)):
		mush.msgDbref(enactor,"You can only clone things and exits.")
		return ("#-1",line)

	# BUGBUG This is not implemented yet. Needs to be completed.

def fnCon(line,enactor,obj):
	(term,line) = getOneTerm(line,enactor,obj)
	dbref = dbrefify(term,enactor,obj)
	val =  -1 if len(mush.db[dbref].contents) == 0 else mush.db[dbref].contents[0]
	return (str(val),line)

def fnConvSecs(line,enactor,obj):
	(term,line) = getOneTerm(line,enactor,obj)
	secs = numify(term)
	return (str(time.asctime(time.localtime(secs))),line)


def fnOr(line,enactor,obj):

	(terms,line) = getTerms(line,enactor,obj)
	for t in terms:
		if (boolify(t) == True):
			return ("1",line)

	return ("0",line)

def fnCos(line,enactor,obj):
	(term,line) = eval(line,")",enactor,obj)
	rval = math.cos(numify(term))
	line = nextTok(line)
	return (str(rval),line)

def fnCreate(line,enactor,obj):

	(terms,line) = getTerms(line,enactor,obj)
	if (len(terms)<1 or len(terms)>2):
		return ("#-1 Function expects 1 or 2 arguments.",line)

	dbref = mush.db.newObject(mush.db[enactor])
	mush.db[dbref]["NAME"] = terms[0]
	mush.msgDbref(enactor,f"Object named {terms[0]} created with ref #{dbref}.")
	mush.log(2,f"{mush.db[enactor].name}(#{enactor}) created object named {terms[0]} (#{dbref}).")
	return (str(dbref),line)

	
def fnCTime(line,enactor,obj):
	(term,line) =  getOneTerm(line,enactor,obj)
	dbref = dbrefify(term,enactor,obj)
	return (time.ctime(mush.db[dbref].creationTime),line)


#
# takes a *string* as argument, and finds the last integer part and subs one from that.
# so dec(hi3) => hi2, dec(1.2)=>1.1 
# 
def fnDec(line,enactor,obj):

	(term,line) = getOneTerm(line,enactor,obj)
	m = re.search(r'-?\d+$',term)
	
	if (m == None):
		return ("#-1 Argument does not end in integer.",line)

	return (term[0:m.start()]+str(numify(m.group())-1),line)

def fnDefault(line,enactor,obj):

	(terms,line) = getTerms(line,enactor,obj)
	if len(terms) != 2:
		return("#-1 Function exects two arguments.",line)

	(dbref,attr) = getObjAttr(terms[0])
	if (dbref == None):
		return("#-1 Could not decode object and attribute.",line)


	dbref = dbrefify(dbref,enactor,obj)
	attr = attr.upper()
	rval = mush.db[dbref][attr] if attr in mush.db[dbref] else terms[1]

	return (rval,line)

def fnDelete(line,enactor,obj):
	
	(terms,line) = getTerms(line,enactor,obj)
	if len(terms) != 3:
		return("#-1 Function expects three arguments.",line)

	start 	= numify(terms[1])
	length 	= numify(terms[2])

	return (terms[0][0:start]+terms[0][start+length:],line)


def fnDie(line,enactor,obj):
	
	(terms,line) = getTerms(line,enactor,obj)
	if len(terms) != 2:
		return("#-1 Function expects two arguments.",line)

	rolls 	= numify(terms[0])
	sides 	= numify(terms[1])

	return (str(sum([random.randint(1,sides) for x in range(rolls)])),line)

	

def fnDig(line,enactor,obj):
	
	eback = None
	eout = None 

	(terms,line) = getTerms(line,enactor,obj)
	if len(terms) < 1 or len(terms) > 3:
		return("#-1 Function expects one to three arguments.",line)

	if (len(terms) == 3):
		eout = terms[1]
		eback = terms[2]
	if (len(terms)) == 2:
		eout = terms[1]

	return (str(commands.doDig(mush.db[enactor],terms[0],eout,eback)),line)



def fnDist2D(line,enactor,obj):
	
	(terms,line) = getTerms(line,enactor,obj)
	if len(terms) != 4:
		return("#-1 Function expects four arguments.",line)

	x1 = numify(terms[0])
	y1 = numify(terms[1])
	x2 = numify(terms[2])
	y2 = numify(terms[3])
	dist = round(math.sqrt((x2 - x1)*(x2 - x1) + (y2 - y1) * (y2 - y1)),6)

	return (str(dist),line)


def fnDist3D(line,enactor,obj):
	
	(terms,line) = getTerms(line,enactor,obj)
	if len(terms) != 6:
		return("#-1 Function expects six arguments.",line)

	x1 = numify(terms[0])
	y1 = numify(terms[1])
	z1 = numify(terms[2])
	x2 = numify(terms[3])
	y2 = numify(terms[4])
	z2 = numify(terms[5])
	dist = round(math.sqrt((x2 - x1)*(x2 - x1) + (y2 - y1) * (y2 - y1) + (z2 - z1) * (z2 - z1)),6)

	return (str(dist),line)	

def fnDiv(line,enactor,obj):
	
	(terms,line) = getTerms(line,enactor,obj)
	if len(terms) != 2:
		return("#-1 Function expects two arguments.",line)

	a = numify(terms[0])
	b = numify(terms[1])
	
	return (str(a//b),line)


def fnE(line,enactor,obj):
	
	(terms,line) = getTerms(line,enactor,obj)
	if len(terms) != 0:
		return("#-1 Function expects zero arguments.",line)
	
	return ("2.718281",line)

def fnEDefault(line,enactor,obj):

	(terms,line) = getTerms(line,enactor,obj)
	if len(terms) != 2:
		return("#-1 Function exects two arguments.",line)

	(dbref,attr) = getObjAttr(terms[0])
	if (dbref == None):
		return("#-1 Could not decode object and attribute.",line)

	dbref = dbrefify(dbref,enactor,obj)
	attr = attr.upper()
	(rval,empty) = eval(mush.db[dbref][attr] if attr in mush.db[dbref] else terms[1],"",enactor,obj)
	return (rval,line)

def fnEdit(line,enactor,obj):
	
	(terms,line) = getTerms(line,enactor,obj)
	if len(terms) != 3:
		return("#-1 Function expects three arguments.",line)

	if (terms[1] == '$'):
		s = terms[0] + terms[2]
	elif (terms[1] == '^'):
		s = terms[2] + terms[0]
	else:
		s = terms[0].replace(terms[1],terms[2])
	
	return (s,line)

def fnElement(line,enactor,obj):
	
	(terms,line) = getTerms(line,enactor,obj)
	
	# Not sure why this is what is returned in these cases, but preserved for pennmush compatibility.
	if (len(terms) == 0):
		return ("1",line)
	if (len(terms) == 1):
		return ("0",line)

	l = terms[0].split(' ' if len(terms) < 3 else terms[2][0])
	
	c = 1
	for item in l: 
		if fnmatch.fnmatch(item,terms[1]):
			return (str(c),line)
		c+=1
	
	return ("0",line)


def fnElements(line,enactor,obj):
	
	(terms,line) = getTerms(line,enactor,obj)
	
	if (len(terms) < 2 or len(terms) > 3):
		return ("#-1 Function expects two or three arguments.",line)

	sep = terms[2][0] if len(terms) == 3 else ' '
	elements = terms[0].split(sep)
	indices = terms[1].split()
	rval = []

	for i in indices:
		rval.append(elements[numify(i)-1])

	return (sep.join(rval),line)

def fnEmit(line,enactor,obj):
	(term,line) = getOneTerm(line,enactor,obj)
	mush.msgLocation(mush.db[obj].location,term)
	return ("",line)

def fnEnumerate(line,enactor,obj):
	
	(terms,line) = getTerms(line,enactor,obj)

	sep = ' ' if len(terms) < 2 else terms[1][0]
	connective = 'and' if len(terms) < 3 else terms[2]
	items = terms[0].split(sep)

	if len(items) < 2:
		return (terms[0],line)

	if len(items) == 2:
		return (f"{items[0]} {connective} {items[1]}",line)

	return (", ".join(items[:-1])+", " + connective + " " + items[-1],line)

def fnEq(line,enactor,obj):

	(terms,line) = getTerms(line,enactor,obj)
	
	if (len(terms) != 2):
		return ("#-1 Function expects two arguments",line)

	if (not isnum(terms[0] or not isnum(terms[1]))):
		return ("#-1 Arguments must be numbers",line)

	return ("1" if numify(terms[0]) == numify(terms[1]) else "0",line)


def escaper(match):
	return f"\\{match.group(0)}"

def fnEscape(line,enactor,obj):


	# call eval in special "escaping" mode
	(term,line) = eval(line,")",enactor,obj,True)
	line = nextTok(line)
	term = "\\" + re.sub(r"[%;{}\[\]]",escaper,term)
	
	return (term,line)

def fnEval(line,enactor,obj):
	
	(terms,line) = getTerms(line,enactor,obj)
	if (len(terms) != 2):
		return ("#-1 Function expects two arguments.",line)

	dbref = dbrefify(terms[0],enactor,obj)
	attr = terms[1].upper()
	if attr in mush.db[dbref]:
		(term,ignore) = eval(mush.db[dbref][attr],"",enactor,obj)
		return (term,line)

	return ("",line)

#
# weird functino. Based on documentation, returns the first exit for object. 
# does so if its a room. 
# otherwise, returns the first room in the location chain of the object.
# for instance -- player in room X carrying object key:
# th exit(key) -> returns dbref(X)
#	
def fnExit(line,enactor,obj):

	(terms,line) = getTerms(line,enactor,obj)
	if (len(terms) == 0):
		return ("#-1",line)

	dbref = dbrefify(terms[0])
	
	if mush.db[dbref].flags & ObjectFlags.ROOM:
		for o in mush.db[dbref].contents:
			if mush.db[o].flags & ObjectFlags.EXIT:
				return (str(o),line)
	else:
		while not mush.db[mush.db[dbref].location].flags & ObjectFlags.ROOM:
			dbref = mush.db[dbref].location
	
	return (str(dbref),line)


def fnExp(line,enactor,obj):
	(term,line) = getOneTerm(line,enactor,obj)
	return (str(round(math.exp(numify(term)),6)),line)


def fnExtract(line,enactor,obj):
	
	(terms,line) = getTerms(line,enactor,obj)

	if (len(terms) < 3 or len(terms) > 4):
		return ("#-1 Function expects 3 or 4 arguments",line)


	sep = ' ' if len(terms) < 4 else terms[3][0]
	start = numify(terms[1]) - 1
	length = numify(terms[2]) 
	items = terms[0].split(sep)

	return (sep.join(items[start:start+length]),line)


def fnFDiv(line,enactor,obj):
	
	(terms,line) = getTerms(line,enactor,obj)
	if len(terms) != 2:
		return("#-1 Function expects two arguments.",line)

	return (str(round(numify(terms[0])/numify(terms[1]),6)),line)

def fnFilter(line,enactor,obj):

	(terms,line) = getTerms(line,enactor,obj)
	if (len(terms)<2 or len(terms) > 3):
		return ("#-1 Function expects two or three arguments.",line)

	(dbref,attr) = getObjAttr(terms[0])
	#
	# BUGBUG Not complete.
	#
	return ("",line)

def fnFirst(line,enactor,obj):
	(terms,line) = getTerms(line,enactor,obj)
	if (len(terms) > 2):
		return("#-1 Function expects one or two arguments.",line)

	# and empty set of arguements returns empty.
	if (len(terms) == 0):
		return("",line)

	sep = ' ' if len(terms) != 2 else terms[1][0]
	return (terms[0].split(sep)[0],line)


def fnFlip(line,enactor,obj):
	(term,line) = getOneTerm(line,enactor,obj)
	return (term[::-1],line)

def fnFloor(line,enactor,obj):
	(s,line) = getOneTerm(line,enactor,obj)
	return (str(math.floor(numify(s))),line)

def fnForEach(line,enactor,obj):

	(terms,line) = getTerms(line,enactor,obj)
	if (len(terms) != 2):
		return("#-1 Function expects two arguments.",line)

	(dbref,attr) = getObjAttr(terms[0])
	if (dbref == None):
		return("#-1 Could not decode object and attribute.",line)

	dbref = dbrefify(dbref,enactor,obj)

	if attr in mush.db[dbref]:
		rVal = ""
		for letter in terms[1]:
			
			gRegisters[0] = letter
			(term,ignore) = eval(mush.db[dbref][attr],"",enactor,obj)
			rVal += term 
	else:
		return ("",line)

	return (rVal,line)


def fnFreeAttr(line,enactor,obj):
	
	(terms,line) = getTerms(line,enactor,obj)
	if (len(terms) != 3):
		return("#-1 Function expects three arguments.",line)

	n = 0
	dbref = dbrefify(terms[0],enactor,obj)
	prefix = terms[1].upper()
	suffix = terms[2].upper()
	while True:
		if not f"{prefix}{n}{suffix}" in mush.db[dbref]:
			return (str(n),line)
		n+=1


	return ("-1",line)

def fnFullName(line,enactor,obj):

	(term,line) = getOneTerm(line,enactor,obj)
	dbref = -1 if term == "" else dbrefify(term,enactor,obj)

	return (mush.db[dbref]["NAME"],line)

	
def fnFunctions(line,enactor,obj):
	(unused,line) = getOneTerm(line,enactor,obj)
	return (' '.join(fnList.keys()),line)


def fnGet(line,enactor,obj):

	(term,line) = getOneTerm(line,enactor,obj)
	if (term == ""):
		return("#-1 Function expects one argument.",line)

	(dbref,attr) = getObjAttr(term)
	if (dbref == None):
		return("#-1 Could not decode object and attribute.",line)

	dbref = dbrefify(dbref,enactor,obj)
	return ("" if attr not in mush.db[dbref] else mush.db[dbref][attr],line)

def fnGet_Eval(line,enactor,obj):
	
	(term,line) = getOneTerm(line,enactor,obj)
	if (term == ""):
		return ("#-1 Function expects two arguments.",line)
	(dbref,attr) = getObjAttr(term)
	if (dbref == None):
		return("#-1 Could not decode object and attribute.",line)

	dbref = dbrefify(dbref,enactor,obj)
	if attr in mush.db[dbref]:
		(term,ignore) = eval(mush.db[dbref][attr],"",enactor,obj)
		return (term,line)

	return ("",line)


def fnGrab(line,enactor,obj):
	
	(terms,line) = getTerms(line,enactor,obj)
	if (len(terms) < 2 or len(terms) > 3):
		return ("#-1 Function expects two or three arguments.",line)
	
	sep = terms[2][0] if len(terms) == 3 else ' '
	elements = terms[0].split(sep)
	pattern = terms[1]
	
	for item in elements: 
		if fnmatch.fnmatch(item,pattern):
			return (item,line)
		
	return ("",line)


def fnGrabAll(line,enactor,obj):
	
	(terms,line) = getTerms(line,enactor,obj)
	if (len(terms) < 2 or len(terms) > 3):
		return ("#-1 Function expects two or three arguments.",line)
	
	sep = terms[2][0] if len(terms) == 3 else ' '
	elements = terms[0].split(sep)
	pattern = terms[1]
	return (sep.join([x for x in elements if fnmatch.fnmatch(x,pattern)]),line)



def fnGt(line,enactor,obj):

	(terms,line) = getTerms(line,enactor,obj)
	
	if (len(terms) != 2):
		return ("#-1 Function expects two arguments",line)

	if (not isnum(terms[0] or not isnum(terms[1]))):
		return ("#-1 Arguments must be numbers",line)

	return ("1" if numify(terms[0]) > numify(terms[1]) else "0",line)



def fnGte(line,enactor,obj):

	(terms,line) = getTerms(line,enactor,obj)
	
	if (len(terms) != 2):
		return ("#-1 Function expects two arguments",line)

	if (not isnum(terms[0] or not isnum(terms[1]))):
		return ("#-1 Arguments must be numbers",line)

	return ("1" if numify(terms[0]) >= numify(terms[1]) else "0",line)



def fnHasAttr(line,enactor,obj):

	(terms,line) = getTerms(line,enactor,obj)
	
	if (len(terms) != 2):
		return ("#-1 Function expects two arguments",line)

	dbref = dbrefify(terms[0],enactor,obj)
	return ("1" if dbref != None and terms[1].upper() in mush.db[dbref] else "0",line)


def fnHasFlag(line,enactor,obj):

	(terms,line) = getTerms(line,enactor,obj)
	
	if (len(terms) != 2):
		return ("#-1 Function expects two arguments",line)

	(dbref,attr) = getObjAttr(terms[0])
	dbref = dbrefify(dbref,enactor,obj)

	if (attr != None):
		return ("#-1 function not implemented for attribute flags.")

	flag = None
	for x in ObjectFlags:
		if (x.name  == terms[1].upper()):
			flag = x
			break


	return ("1" if flag & mush.db[dbref].flags else "0",line)




def fnHasType(line,enactor,obj):

	(terms,line) = getTerms(line,enactor,obj)
	
	if (len(terms) != 2):
		return ("#-1 Function expects two arguments",line)

	dbref = dbrefify(terms[0],enactor,obj)

	t = terms[1].upper()


	if t not in ["ROOM","PLAYER","EXIT","THING"]:
		return ("#-1 Unsupported type.",line)

	if (t == "ROOM" and mush.db[dbref].flags & ObjectFlags.ROOM) or \
		(t == "PLAYER" and mush.db[dbref].flags & ObjectFlags.PLAYER) or \
		(t == "EXIT" and mush.db[dbref].flags & ObjectFlags.EXIT) or \
		(t == "THING" and not mush.db[dbref].flags & (ObjectFlags.ROOM | Objectflags.PLAYER | ObjectFlags.EXIT)):
		return ("1",line)

	return ("0",line)




def fnHome(line,enactor,obj):

	(term,line) = getOneTerm(line,enactor,obj)
	if (term == ""):
		return("#-1 Function expects one argument.",line)
	dbref = dbrefify(term,enactor,obj)
	return (f"#{mush.db[dbref].home}",line)


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
	'CENTER'	: fnCenter,
	'CHANGE'	: fnNotImplemented, # Elendor specific
	'CLONE'		: fnNotImplemented,
	'CMDS'		: fnNotImplemented,
	'COMP'		: fnComp,
	'CON'		: fnCon,
	'CONN'		: fnNotImplemented,
	'CONTROLS'	: fnNotImplemented,
	'CONVFIRSTON': fnNotImplemented,
	'CONVSECS'	: fnConvSecs,
	'CONVTIME'	: fnNotImplemented,
	'COR'		: fnOr,
	'COS'		: fnCos,
	'CREATE'	: fnCreate,
	'CSTATS'	: fnNotImplemented,
	'CTIME'		: fnCTime,
	'DEC'		: fnDec,
	'DECRYPT'	: fnNotImplemented,
	'DEFAULT'	: fnDefault,
	'DELETE'	: fnDelete,
	'DESCFUN'	: fnNotImplemented,
	'DIE'		: fnDie,
	'DIG'		: fnDig,
	'DIST2D'	: fnDist2D,
	'DIST3D' 	: fnDist3D,
	'DIV'		: fnDiv,
	'DOING'		: fnNotImplemented,
	'E'			: fnE,
	'EDEFAULT'	: fnEDefault,
	'EDIT'		: fnEdit,
	'ELEMENT'	: fnElement,
	'ELEM'		: fnElement,
	'ELEMENTS'	: fnElements,
	'ELOCK'		: fnNotImplemented,
	'EMIT'		: fnEmit,
	'ENCRYPT'	: fnNotImplemented,
	'ENTRANCES'	: fnNotImplemented,
	'ENUMERATE'	: fnEnumerate,
	'EQ'		: fnEq,
	'ESCAPE'	: fnEscape,
	'EVAL'		: fnEval,
	'EVALTHUNKS': fnNotImplemented, # Elendor specific...
	'EXIT'		: fnExit,
	'EXP'		: fnExp,
	'EXTRACT'	: fnExtract,
	'FDIV'		: fnFDiv,
	'FILTER'	: fnFilter,
	'FINDABLE'	: fnNotImplemented,
	'FIRST'		: fnFirst,
	'FLAGS'		: fnNotImplemented,
	'FLIP'		: fnFlip,
	'FLOOR'		: fnFloor,
	'FOLD'		: fnNotImplemented,
	'FORCE'		: fnNotImplemented,
	'FOREACH'	: fnForEach,
	'FREEATTR'	: fnFreeAttr,
	'FULLNAME'	: fnFullName,
	'FUNCTIONS' : fnFunctions,
	'GET'		: fnGet,
	'GET_EVAL'	: fnGet_Eval,
	'GRAB'		: fnGrab,
	'GRABALL'	: fnGrabAll,
	'GREP'		: fnNotImplemented,
	'GREPI'		: fnNotImplemented,
	'GT'		: fnGt,
	'GTE'		: fnGte,
	'HASATTR'	: fnHasAttr,
	'HASATTRVAL': fnHasAttr,
	'HASATTRP'	: fnNotImplemented,
	'HASATTRPVAL': fnNotImplemented,
	'HASFLAG'	: fnHasFlag,
	'HASPOWER'	: fnNotImplemented,
	'HASTHUNK'	: fnNotImplemented,
	'HASTYPE'	: fnHasType,
	'HIDDEN'	: fnNotImplemented,
	'HILITE'	: fnNotImplemented,
	'HOME'		: fnHome,
	'HTMLESCAPE': fnNotImplemented,
	'HTMLOK'	: fnNotImplemented,









}

def testParse():

	tests= [


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
		"center(Hello World,40,-)",
		"comp(abc,abc)",
		"comp(Abc,abc)",
		"comp(abc,Abc)",
		"convsecs(123456)",
		"create(dog,30)",
		"ctime(me)",
		"dec(312)",
		"dec(dog12)",
		"dec(dog-1)",
		"default(me/description,so weird)",
		"default(me/yoyo,Not a yoyo here.",
		"[delete(abcdefgh, 3, 2)]",
		"die(10,100)",
		"die(3,6)",
		"dig(house)",
		"dig(house,out,in)",
		"dist2D(1,1,3,3)",
		"dist3D(1,1,1,3,3,3)",
		"div(5,2)",
		"e()",
		"edefault(me/yoyo,so w[e()]ird)",
		"edit(dog house,dog,cat)",
		"edit(dog house,$,cat)",
		"edit(dog house,^,cat)",
		"elem(this is a test,is, )",
		"element(this|is|a|test,is,|)",
		"elem(this is a test,t?st, )",
		"elements(Foof|Ack|Beep|Moo,3 1,|)",
		"elements(Foo Ack Beep Moo Zot,2 4)",
		"emit(foo)",
		"enumerate(foo bar)",
		"enumerate(foo bar baz)",
		"enumerate(foo|bar|baz,|,doggie)",
		"eq(a,b)",
		"eq(1,2,3)",
		"eq(2,2)",
		"eq(2,1)",
		"escape(hello world[ dog % ; ] { } hah!)",
		"eval(me,description)",
		"exp()",
		"exp(0)",
		"exp(1)",
		"exp(2)",
		"extract(a|b|c|d,2,2,|)",
		"extract(a dog in the house went bark,2,4)",
		"extract(a dog,4,5)",
		"first()",
		"first(dog house)",
		"first(dog^house^was,^)",
		"flip(foo bar baz)",
		"floor(23.12)",
		"add(1,1)",
		"foreach(me/addone,123456)",
		"freeattr(me,test,foo)",
		"fullname(me)",
		"functions()[fullname(me)]",
		"get(me/nothing)",
		"get(me/test1foo)",
		"grab(dog|cat|horse|mouse|house|help,h*,|)",
		"graball(dog|cat|horse|mouse|house|help,h*,|)",
		"hasattr(dog,cat)",
		"hasattr(me,cat)",
		"hasattr(me,test1foo)",
		"hasflag(me,god)",
		"hasflag(me,eXit)",
		"hastype(me,DOG)",
		"hastype(me,EXIT)",
		"hastype(me,PLAYER)",
		"home(me)"

		]



	mush.db[1]["ADDONE"]="add(%0,1)"
	mush.db[1]["TEST1FOO"]="FOOBAR"
	mush.db[1]["TEST0FOO"]="FOOBAR"

	for s in tests:
		clearRegs()
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
	elif (ch in '0123456789'):

		return gRegisters[int(ch)]

	# BUGBUG: Need to add other substitutions
	return ''




def eval(line,stops,enactor,obj,escaping=False):

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
	pattern = re.compile(f"[{stops}\[%]") if not escaping else re.compile(f"[{stops}]")
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
				line = line[i+2:]
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















