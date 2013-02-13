"""
Popbak makes it easy to back up a POP accessible email in box

The email parsing portion of the code is based on code that I got from Larry Bates here:
http://mail.python.org/pipermail/python-list/2004-June/265634.html

author -- Jay Marcyes <jay@marcyes.com>

todo -- this script is like 6 years old now and so there are some naming problems (eg, I used camelCase
    method names, some indents are 2 spaces, others 4) that I need to clean up,
    I went through and fixed some of the issues, but not all, I'm just happy it still works after all this time
"""

import poplib
import email
import email.Parser
import os
import sys
import errno
import mimetypes
import re
import time
from datetime import date
from types import *

class Echo(object):
    """
    simple class that wraps print, why? so I can handle verbosity levels in one place
    """

    verbosity = 0

    @classmethod
    def stdout(cls, format_msg, *args, **kwargs):
        '''
        print format_msg to stdout, taking into account verbosity level
        '''
        if not cls.verbosity: return
        print format_msg.format(*args)
        return

    @classmethod
    def stderr(cls, format_msg, *args, **kwargs):
        '''
        print format_msg to stderr
        '''
        sys.stderr.write("{}\n".format(format_msg.format(*args)))
        sys.stderr.flush()
        return

    @classmethod
    def err(cls, e):
        '''
        print an exception message to stderr
        '''
        cls.sdterr(e.message)

class EmailAttachment:
    def __init__(self, messagenum, attachmentnum, filename, contents):
        '''
        arguments:

        messagenum - message number of this message in the Inbox
        attachmentnum - attachment number for this attachment
        filename - filename for this attachment
        contents - attachment's contents
        '''
        self.messagenum = messagenum
        self.attachmentnum = attachmentnum
        self.filename = filename
        self.contents = contents
        return

    def save(self, savepath, savefilename=None):
        '''
        Method to save the contents of an attachment to a file
        arguments:

        savepath - path where file is to be saved
        safefilename - optional name (if None will use filename of attachment
        '''

        savefilename = savefilename or self.filename
        
        if self.contents:
          attached_file = os.path.join(savepath, savefilename)
          try:
            f=open(attached_file,"wb")
            f.write(self.contents)
            f.close()
          except IOError, e:
            Echo.stderr("Could not save {}: IO error({}): {}, moving on...", attached_file, e.errno, e.strerror)
          except:
            Echo.stderr("Could not save ({}), moving on...", attached_file)
        return

class EmailMsg:
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
                    self.ATTACHMENTS.append(EmailAttachment(messagenum,attachmentnum,filename,part.get_payload(decode=1)))
                    Echo.stdout("Attachment filename = {}", filename.encode("utf-8"))

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
        Echo.stderr(emsg)
        #sys.exit(emsg)
        return ""
    
    def toHeader(self):
      try:
        return self.msg.get('To')
      except:
        emsg="email_msg-Unable to get to header"
        Echo.stderr(emsg)
        #sys.exit(emsg)
        return ""
            
    def fromEmail(self):
        try:
          from_email = re.sub("[\n\r\t \"]","",self.fromHeader())
          from_email = re.sub(".*<([^>]*)>.*","\\1",from_email)
          return from_email
        except:
            emsg="email_msg-Unable extract from email address"
            Echo.stderr(emsg)
            #sys.exit(emsg)
            return ""
            
    def fromHeader(self):
      try:
        return self.msg.get('From')
      except:
          emsg="email_msg-Unable to get from header"
          Echo.stderr(emsg)
          #sys.exit(emsg)
          return ""
    
    def date(self):
        try: return self.msg.get('Date')
        except:
            emsg="email_msg-Unable to get Date information"
            Echo.stderr(emsg)
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
            Echo.stderr(emsg)
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
            Echo.stderr(emsg)
            #sys.exit(emsg)
            return ""

    def get(self, key):
        try: return self.msg.get(key)
        except:
            emsg="email_msg-Unable to get email key=%s information" % key
            Echo.stderr(emsg)
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
              Echo.stdout("saving: {}: {} in {}", acounter, a.filename.encode("utf-8"), filepath)
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
        Echo.stderr("Could not save {}: IO error({}): {}, moving on...", attached_file, e.errno, e.strerror)
      except:
        Echo.stderr("Could not save email body in {}, moving on...", filepath)

      return
        

class Pop3Inbox:
    def __init__(self, server, port, userid, password):
        self.result=0             # Result of server communication
        self.MESSAGES=[]          # List for storing message objects
        self.messages_index=0     # Index of message for next method
        
        Echo.stdout("Entering")
        Echo.stdout("{}, {}, {}, {}".format(server, port, userid, password))
        
        # See if I can connect using information provided
        try:
            Echo.stdout("Calling poplib.POP3_SSL(server, port)")
            self.connection=poplib.POP3_SSL(server,port)
            Echo.stdout("Calling connection.user(userid)")
            self.connection.user(userid)
            Echo.stdout("Calling connection.pass_(password)")
            self.connection.pass_(password)

        except Exception, e:
            if self.connection: self.connection.quit()
            raise e

        # Get count of messages and size of mailbox
        Echo.stdout("Calling connection.stat()")
        self.msgcount, self.size=self.connection.stat()
        Echo.stdout("msgcount: {}, size: {}", self.msgcount, self.size)

        # Loop over all the messages processing each one in turn
        for msgnum in range(1, self.msgcount+1):
            self.MESSAGES.append(EmailMsg(msgnum,self.connection.retr(msgnum)))

        Echo.stdout("Leaving")
        return

    def close(self):
        self.connection.quit()
        return

    def remove(self, msgnumorlist):
        if isinstance(msgnumorlist, int): self.connection.dele(msgnumorlist)
        elif isinstance(msgnumorlist, (list, tuple)): map(self.connection.dele, msgnumorlist)
        else:
            raise RuntimeError("remove - msgnumorlist must be type int, list, or tuple, not {}".format(type(msgnumorlist)))

        return

    def __iter__(self):
        return self

    def next(self):
        # Try to get the next attachment
        try: MESSAGE=self.MESSAGES[self.messages_index]
        except:
            self.messages_index=0
            raise StopIteration()
        # Increment the index pointer for the next call
        self.messages_index+=1
        return MESSAGE

if __name__ == "__main__":

    import argparse
    # http://docs.python.org/library/argparse.html#module-argparse
    parser = argparse.ArgumentParser(description='Easily backup a POP accessible email account')
    parser.add_argument("-u", "--username", dest="userid", default="", help="Your email username (eg, username@example.com)")
    parser.add_argument("-p", "--password", dest="password", default="", help="Your email password")
    parser.add_argument("-s", "--server", dest="server", default="pop.gmail.com", help="The server you want to connect to")
    parser.add_argument("-o", "--port", dest="port", default=995, type=int, help="The port you want to connect to")
    parser.add_argument("-v", "--verbose", dest="verbosity", action='count', help="the verbosity level, more v's, more output")
    parser.add_argument("--version", action='version', version="%(prog)s 0.3")
    parser.add_argument("-d", "--dir", dest="dir", default=date.today(), help="the directory to backup to")

    options = parser.parse_args()
    total = 0
    Echo.verbosity = options.verbosity
    
    while 1:
      
        Echo.stdout("CONNECTING")

        try:
            inbox=Pop3Inbox(options.server, options.port, options.userid, options.password)

        except Exception, e:
            Echo.err(e)
            sys.exit(2)

        Echo.stdout("Message count={}, Inbox size={}", inbox.msgcount, inbox.size)

        if not inbox.msgcount:
            inbox.close()
            break
  
        counter = 0
        for m in inbox:
            counter += 1
            total += 1
            
            #print "To: %s" % m.toEmail()
            #print "From: %s" % m.fromEmail()
            #print "Content-Type: %s" % m.contentType()
            #print "Subject: %s" % m.subject()
            #print "-------------Message (%i) body lines---------------" % counter
            #print m.body()
            #print "-------------End message (%i) body lines-----------" % counter
            
            Echo.stdout("saving ({}) {}", total, m.subject())
            m.save(options.dir)
  
        # uncomment if I want to delete the messages, though this is a backup script, so
        # why would I want to?
        #if inbox.msgcount: inbox.remove(range(1, inbox.msgcount+1))

        inbox.close() # close the connection
        Echo.stdout("Resting for 5 seconds before reconnecting to check for more messages.")
        time.sleep(5)

