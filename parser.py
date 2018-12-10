
import re
from mushstate import mush


def evalString(s,enactor,obj=-1):
	return EvalEngine(s,enactor,enactor if obj == -1 else obj).eval("")

def evalAttribute(dbref,attr,enactor):
	return evalString(mush.db[dbref][attr.upper()],enactor,dbref) if attr.upper() in mush.db[dbref] else ""

class EvalEngine:

	def __init__(self,line,enactor,obj):

		self.enactor 		= enactor
		self.obj     		= obj
		self.line    		= line
		self.originalLine	= line
		self.substack		= [] # for saving context of substitutions.
		self.saved 			= [] # for saving context.

		self.sub = {
			"%0":"","%1":"","%2":"","%3":"","%4":"","%5":"","%6":"","%7":"","%8":"","%9":"", # registers
			"##": "", 									# ## (List Element in iter)
			"#@": "", 									# #@ (List Position in iter)
			"#$": "",									# #$ (Switch test in switch)
			"%N": mush.db[self.enactor].name, 			# %N (enactor name)
			"%#": self.enactor,							# %# (enactor dbref)
			"%L": mush.db[self.enactor].location, 		# %L (enactor location)
			"%!": self.obj, 							# %! (object dbref)
			"%c": self.originalLine,					# %c (command)
			"%?": "#-1 Not implemented.",				# %? (function invocation count)
			"%R": "\n",									# %R (newline)
			"%B": " ",									# %B (space)
			"%t": "\t",									# %t (tab)
	}
		
	def save(self):
		self.saved.append(self.enactor)
		self.saved.append(self.obj)
		self.saved.append(self.line)
		self.saved.append(self.originalLine)
		self.saved.append(self.sub)
		
	def restore(self):
		self.sub 			= self.saved.pop()
		self.originalLine 	= self.saved.pop()
		self.line 			= self.saved.pop()
		self.obj 			= self.saved.pop()
		self.enactor 		= self.saved.pop()

	def splitTerms(self,s):

		terms 		= []
		plevel 		= 1
		blevel 		= 0
		i 			= 0
		termStart 	= 0


		while (plevel or blevel) and i < len(s):
			if s[i] == ')':
				plevel -=1
				if (plevel == 0):
					terms.append(s[termStart:i])
			elif s[i] == '(':
				plevel +=1
			elif s[i] == ']':
				blevel -=1
			elif s[i] == '[':
				blevel +=1
			elif (s[i] == ',' and plevel == 1 and blevel == 0):
				terms.append(s[termStart:i])
				termStart = i+1
			i+=1
		
		if (i == len(s)):
			terms.append(s[termStart:])

		return terms
	
	def dbrefify(self,term):

		term = term.strip().upper()

		if (term == "" or term=="HERE"):
			return mush.db[self.enactor].location # assume no argument defaults to current location of enactor

		if (term == "ME"):
			return self.enactor

		# look in the contents of the current room
		for d in mush.db[mush.db[self.enactor].location].contents:
			if (mush.db[d].aliasMatch(term)):
				return d 

		# look in inventory
		for d in mush.db[self.enactor].contents:
			if (mush.db[d].aliasMatch(term)):
				return d

		if (term[0] == '#' and term[1:].isnumeric()):
			dbref = self.numify(term[1:])	
			if mush.db.validDbref(dbref) and (mush.db[dbref].location == mush.db[self.enactor].location or mush.db[dbref].location == self.enactor or \
				mush.db[dbref].owner == self.enactor or mush.db[self.enactor].flags & ObjectFlags.WIZARD):
				return dbref

		return None

	#
	# For Mush functions
	# A negative dbref (#-) is considered false
	# The number 0 is considered false
	# An empty string is considered false
	# None string is considered false.
	# anything else is True.
	# 
	def boolify(self,term):
		if (term == None):
			return False
		if (term[0:2] == '#-'): 
			return False
		if (len(term) == 0): 
			return False
		if (self.isnum(term)):
			return self.numify(term) != 0

		return True

	def isInt(self,string):
		try: 
			int(string)
			return True
		except ValueError:
			return False

	def isFloat(self,string):
	    try:
	        float(string)
	        return True
	    except ValueError:
	        return False

	def isnum(self,term):
		return self.isInt(term) or self.isFloat(term)

	def numify(self,term):

		if (self.isInt(term)):
			val = int(term)
		elif(self.isFloat(term)):
			val = float(term)
		else:
			val = 0

		return val

	def getObjAttr(self,term):

		sep = term.find('/')
		if (sep == -1):
			return (self.dbrefify(term),None)
		return (self.dbrefify(term[0:sep]),term[sep+1:].upper())

	def _get_fn_terms(self):

		plevel 			= 1
		blevel 			= 0
		i 				= 1
		while (plevel or blevel) and i < len(self.line):
			if self.line[i] == ')':
				plevel -=1
			elif self.line[i] == '(':
				plevel +=1
			elif self.line[i] == ']':
				blevel -=1
			elif self.line[i] == '[':
				blevel +=1
			i+=1

		term = self.line[1:i-1] if not plevel else self.line[1:]		
		self.line = self.line[i:] if i < len(self.line) else ""
		return term

	def _eval_fn(self):

		rStr = ""
		self.line = self.line.strip()

		# look for first term...
		match = re.search(r'\W',self.line)
		if (match):
			# extract the term.
			i = match.start()
			term = "fn_"+self.line[:i].lower()

			# if the term is the name of a function, call that function, with an argument of the rest of the string.
			if self.line[i]=='(' and hasattr(gMushFunctions,term):
				self.line = self.line[i:]
				terms = self._get_fn_terms()
				rStr += getattr(gMushFunctions,term)(self,terms)
			else: 
				# Not a match, so simply add what we found so far to the results string and update the line.
				rStr += self.line[0:i]
				self.line = self.line[i:]

		return rStr

	# instead of continuing with current line, evaluates a different string with the same context.
	def stringEval(self,s):
		self.save()
		self.line = s
		self.originalLine = s
		s = self.eval("")
		self.restore()
		return s 
		
	def attrEval(self,dbref,attr):
		return "" if attr not in mush.db[dbref] else self.stringEval(mush.db[dbref][attr])
	
	def evalTerms(self,terms):
		results = []
		for term in self.splitTerms(terms):
			results.append(self.stringEval(term) if term != " " else " ")
		return results

	def evalOneTerm(self,term):
		return self.stringEval(term)

	def eval(self,stops):
		
		rStr = ""

		# ignore empty lines.
		if (self.line == None):
			return ""
			
		# first part of a line is always in fn evaluation mode.
		rStr += self._eval_fn()

		# Now loop through the rest of the string until we reach our stopchars or a special char.
		specialchars = "\[%#]"
		pattern = re.compile(f"[{stops}{specialchars}") 

		while self.line != None:

			match = pattern.search(self.line)
			if (not match): 
				# No more special characters until the end of the string. 
				rStr += self.line 
				self.line = None 
			else:
				i = match.start() 
				rStr += self.line[:i]
				# Check for substitution characters
				if self.line[i] == '%' or self.line[i] == '#':
					rStr += self.sub[self.line[i:i+2]] if self.line[i:i+2] in self.sub else self.line[i:i+2]
					self.line = self.line[i+2:]
				elif self.line[i] == '[':
					self.save()
					self.line = self.line[i+1:]
					self.originalLine = self.line 
					rStr += self.eval("]")
					line = self.line 
					self.restore()
					self.line = None if line == None else line[1:]
						
				# we must have found one of the stop chars. exit.
				else:
					self.line = self.line[i:]
					return rStr

		return rStr


gMushFunctions = getattr(__import__("mushfun"), "MushFunctions")()
