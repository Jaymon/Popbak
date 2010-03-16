'''
from: http:///lab.noopsi.com/popbak/
questions, comments, fanmail goes to lab@noopsi.com
license: LGPL - http://www.gnu.org/copyleft/lesser.html
'''


import poplib
import email
import email.Parser
import os
import sys
import errno
import mimetypes
import re
import time
import optparse
from datetime import date
from types import *

"""
This is based on code that I got from Larry Bates here:
http://mail.python.org/pipermail/python-list/2004-June/265634.html
"""

class email_attachment:
    def __init__(self, messagenum, attachmentnum, filename, contents):
        '''
        arguments:

        messagenum - message number of this message in the Inbox
        attachmentnum - attachment number for this attachment
        filename - filename for this attachment
        contents - attachment's contents
        '''
        self.messagenum=messagenum
        self.attachmentnum=attachmentnum
        self.filename=filename
        self.contents=contents
        return

    def save(self, savepath, savefilename=None):
        '''
        Method to save the contents of an attachment to a file
        arguments:

        savepath - path where file is to be saved
        safefilename - optional name (if None will use filename of attachment
        '''

        savefilename=savefilename or self.filename
        
        if self.contents:
          attached_file = os.path.join(savepath, savefilename)
          try:
            f=open(attached_file,"wb")
            f.write(self.contents)
            f.close()
          except IOError, e:
            print "Could not save %s: IO error(%s): %s, moving on..." % (attached_file,e.errno, e.strerror)
          except:
            print "Could not save (%s), moving on..." % attached_file
        return





class email_msg:
    def __init__(self, messagenum, contents):
        self.messagenum=messagenum
        self.contents=contents
        self.attachments_index=0  # Index of attachments for next method
        self.ATTACHMENTS=[]       # List of attachment objects
        self.body_text = "";

        self.msglines='\n'.join(contents[1])
        #
        # See if I can parse the message lines with email.Parser
        #
        self.msg=email.Parser.Parser().parsestr(self.msglines)
        if self.msg.is_multipart():
            attachmentnum=0
            for part in self.msg.walk():
                # multipart/* are just containers
                mptype=part.get_content_maintype()
                filename = part.get_filename()
                if mptype == "multipart": continue
                if filename: # Attached object with filename
                    attachmentnum+=1
                    self.ATTACHMENTS.append(email_attachment(messagenum,attachmentnum,filename,part.get_payload(decode=1)))
                    print "Attachment filename=%s" % filename.encode("utf-8")

                else: # Must be body portion of multipart
                    self.body_text=part.get_payload()

        else: # Not multipart, only body portion exists
            self.body_text=self.msg.get_payload()

        return

    def toEmail(self):
      try:
        to_email = re.sub(".*<([^>]*)>.*","\\1",self.toHeader())
        return to_email
      except:
        emsg="email_msg-Unable to extract to email address"
        print emsg
        #sys.exit(emsg)
        return ""
    
    def toHeader(self):
      try:
        return self.msg.get('To')
      except:
        emsg="email_msg-Unable to get to header"
        print emsg
        #sys.exit(emsg)
        return ""
            
    def fromEmail(self):
        try:
          from_email = re.sub("[\n\r\t \"]","",self.fromHeader())
          from_email = re.sub(".*<([^>]*)>.*","\\1",from_email)
          return from_email
        except:
            emsg="email_msg-Unable extract from email address"
            print emsg
            #sys.exit(emsg)
            return ""
            
    def fromHeader(self):
      try:
        return self.msg.get('From')
      except:
          emsg="email_msg-Unable to get from header"
          print emsg
          #sys.exit(emsg)
          return ""
    
    def date(self):
        try: return self.msg.get('Date')
        except:
            emsg="email_msg-Unable to get Date information"
            print emsg
            #sys.exit(emsg)
            return ""
            
    def contentType(self):
        '''
        this doesn't work like I wanted, I wanted to be able to detect either html or
        plain text and then create the appropriate extension, but I don't want to mess
        with it right now
        '''
        try: return self.msg.get('Content-type')
        except:
            emsg="email_msg-Unable to get Content-type information"
            print emsg
            #sys.exit(emsg)
            return ""


    def body(self):
      if self.body_text:
        if type(self.body_text) is StringType: # http://docs.python.org/lib/module-types.html
          return self.body_text
        else: return "message body did not contain valid characters"
      else:
        return "message had no body text"

    def subject(self):
        try:
          if self.msg.get('Subject'):
            return self.msg.get('Subject')
          else:
            return "blank_subject_%s" % re.sub("[^a-zA-Z0-9@(+)_-]*","-",self.date())
        except:
            emsg="email_msg-Unable to get email subject information"
            print emsg
            #sys.exit(emsg)
            return ""

    def get(self, key):
        try: return self.msg.get(key)
        except:
            emsg="email_msg-Unable to get email key=%s information" % key
            print emsg
            #sys.exit(emsg)
            return ""

    def has_attachments(self):
        return (len(self.ATTACHMENTS) > 0)

    def __iter__(self):
        return self

    def next(self):
        #
        # Try to get the next attachment
        #
        try: ATTACHMENT=self.ATTACHMENTS[self.attachments_index]
        except:
            self.attachments_index=0
            raise StopIteration
        #
        # Increment the index pointer for the next call
        #
        self.attachments_index+=1
        return ATTACHMENT

    def save(self,dir):
      email_dir = self.fromEmail()
      fileext = "txt"
      filebase = re.sub("[^a-zA-Z0-9!$@(&+=~ #%.,;)_-]*","",self.subject())
      filebase = filebase[0:30] # keep the filebase to 30 characters in length
      filebase = filebase.strip() # trim the string, strip is deprecated, so after 3.0 this won't work
      filename = "%s.%s" % (filebase,fileext)
      filepath = dir
    
      # make the base dir (where all the emails will go)
      try:
        os.mkdir(filepath)
      except OSError, e:
        # Ignore directory exists error
        if e.errno <> errno.EEXIST: raise
      
      # make the from email dir (each email goes into a folder based on who send it)
      filepath = os.path.join(filepath, email_dir)
      try:
        os.mkdir(filepath)
      except OSError, e:
        # Ignore directory exists error
        if e.errno <> errno.EEXIST: raise
      
      
      # save the email attachments:
      if self.has_attachments():
        try:
          # for some reason, windows folders don't like "..." in the folder, so strip potentially bad stuff like that out
          filepath = os.path.join(filepath, re.sub("[^a-zA-Z0-9@ (+)_-]*","",filebase))
          filepath = filepath.strip() #strip is deprecated, so after 3.0 this won't work
          os.mkdir(filepath)
          
          acounter=0
          for a in self:
              acounter+=1
              print "saving: %i: %s in %s" % (acounter, a.filename.encode("utf-8"), filepath)
              a.save(filepath)
        except OSError, e:
          # Ignore directory exists error
          if e.errno <> errno.EEXIST: raise 
        
      filepath = os.path.join(filepath, filename) 
      
      try:
        fp = open(filepath, 'wb')
        
        fp.write("To: %s\r\n" % self.toHeader())
        fp.write("From: %s\r\n" % self.fromHeader())
        fp.write("Subject: %s\r\n" % self.subject())
        fp.write("Date: %s\r\n\r\n" % self.date())
        fp.write(self.body())
        
        fp.close()
      except IOError, e:
        print "Could not save %s: IO error(%s): %s, moving on..." % (attached_file,e.errno, e.strerror)
      except:
        print "Could not save email body in %s, moving on..." % filepath
        
      return
        




class pop3_inbox:
    def __init__(self, server, port, userid, password):
        self._trace=1
        if self._trace: print "pop3_inbox.__init__-Entering"
        self.result=0             # Result of server communication
        self.MESSAGES=[]          # List for storing message objects
        self.messages_index=0     # Index of message for next method
        
        print "%s, %d, %s, %s\r\n" % (server,port,userid,password)
        
        #
        # See if I can connect using information provided
        #
        try:
            if self._trace: print "pop3_inbox.__init__-Calling poplib.POP3_SSL(server,port)"
            self.connection=poplib.POP3_SSL(server,port)
            if self._trace: print "pop3_inbox.__init__-Calling connection.user(userid)"
            self.connection.user(userid)
            if self._trace: print "pop3_inbox.__init__-Calling connection.pass_(password)"
            self.connection.pass_(password)

        except:
            if self._trace: print "pop3_inbox.__init__-Login failure, closing connection"
            self.result=1
            if self.connection:
              self.connection.quit()

        #
        # Get count of messages and size of mailbox
        #
        if self._trace: print "pop3_inbox.__init__-Calling connection.stat()"
        self.msgcount, self.size=self.connection.stat()
        if self._trace: print "msgcount: %d, size: %d" % (self.msgcount,self.size)
        #
        # Loop over all the messages processing each one in turn
        #
        for msgnum in range(1, self.msgcount+1):
            self.MESSAGES.append(email_msg(msgnum,self.connection.retr(msgnum)))

        if self._trace: print "pop3_inbox.__init__-Leaving"
        return

    def close(self):
        self.connection.quit()
        return

    def remove(self, msgnumorlist):
        if isinstance(msgnumorlist, int): self.connection.dele(msgnumorlist)
        elif isinstance(msgnumorlist, (list, tuple)): map(self.connection.dele, msgnumorlist)
        else:
            emsg="pop3_inbox.remove-msgnumorlist must be type int, list, or tuple, not %s" % type(msgnumorlist)
            print emsg
            sys.exit(emsg)

        return

    def __iter__(self):
        return self

    def next(self):
        #
        # Try to get the next attachment
        #
        try: MESSAGE=self.MESSAGES[self.messages_index]
        except:
            self.messages_index=0
            raise StopIteration
        #
        # Increment the index pointer for the next call
        #
        self.messages_index+=1
        return MESSAGE

if __name__=="__main__":
    
    parser = optparse.OptionParser(usage="%prog -un \"username\" -pw \"password\" -s \"server\" -o \"port\"", version="%prog 0.2")
    parser.add_option("-u", "--username", dest="userid", default="", help="Your email username (eg, username@example.com)")
    parser.add_option("-p", "--password", dest="password", default="", help="Your email password")
    parser.add_option("-s", "--server", dest="server", default="pop.gmail.com", help="The server you want to connect to")
    parser.add_option("-o", "--port", dest="port", default=995, help="The port you want to connect to")
    (options, args) = parser.parse_args()
    
    folder = "%s_%s" % (date.today(),userid)
    
    while 1:
      
      print "CONNECTING"
      
      inbox=pop3_inbox(options.server, options.port, options.userid, options.password)
      if inbox.result:
          emsg="Failure connecting to pop3_inbox"
          print emsg
          sys.exit(emsg)
  
      print "Message count=%i, Inbox size=%i" % (inbox.msgcount, inbox.size)
      
      if not inbox.msgcount:
        inbox.close()
        break
  
      counter=0
      for m in inbox:
          counter+=1
          '''
          print "To: %s" % m.toEmail()
          print "From: %s" % m.fromEmail()
          print "Content-Type: %s" % m.contentType()
          print "Subject: %s" % m.subject()
          print "-------------Message (%i) body lines---------------" % counter
          #print m.body()
          print "-------------End message (%i) body lines-----------" % counter
          '''
          print "saving (%i) %s" % (counter,m.subject())
          m.save(folder)
  
      # uncomment if I want to delete the messages, though this is a backup script, so
      # why would I want to?
      #if inbox.msgcount: inbox.remove(range(1, inbox.msgcount+1))
      
      inbox.close() # close the connection
      print "Resting for 5 seconds before reconnecting to check for more messages."
      time.sleep(5)
