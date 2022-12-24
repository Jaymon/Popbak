# Popbak

Popbak is a Python script that will back up an email account (any email account that supports IMAP access) into a local folder.

I wrote this because I like having an archival copy of my email, I don't want an mbox backup or anything like that, I want an easy way to read the email and see the attachments.

I don't think I described what Popbak does very well, so here's an example, let's say you have 2 emails in your email inbox:

    foo@bar.com "this is my title"
    baz@foo.com "there is a jpg and a pdf file in this email"

Now, if you run Popbak, it will backup the emails in a folder structure like this:

    bakupdir/
      <MAILBOX>/
          bar.com/
            foo@bar.com/
              <DATE> - this is the title.txt/
                body 1.txt
                headers 1.txt
                original.eml
          foo.com/
            baz@foo.com/
              <DATE> - there is a jpg and a pdf file in this email/
                attachment.jpg
                attachment.pdf
                body 1.txt
                headers 1.txt
                original.eml


## How to run from the command line

Backup a mailbox:

    $ python popbak.py backup -u USERNAME -p PASSWORD -s SERVER -o PORT -d "/path/to/backupdir" <MAILBOX>

See all your mailboxes:

    $ python popbak.py mailboxes -u USERNAME -p PASSWORD -s SERVER -o PORT -d

See everything you can do:

    $ python popbak.py --help


### Back up your gmail account

    $ python popbak.py backup -u example@gmail.com -p PASSWORD -d "/path/to/backupdir" "[Gmail]/All Mail" "[Gmail]/Sent Mail"

Make sure you have [activated IMAP access on your gmail account](https://support.google.com/mail/answer/7126229). You might have to [create an app password for Popbak](https://support.google.com/accounts/answer/185833) in your [Google account security settings](https://myaccount.google.com/).

## Installation

Clone this repo:

    $ git clone git@github.com:Jaymon/Popbak.git <DIRECTORY>


Install the dependencies:

    $ cd <DIRECTORY>
    $ pip install -r requirements.txt

Then go ahead and run Popbak using Python 3.7+:

    $ python popbak.py --help
    

## Troubleshooting

[Make sure you don't backup too much per day](https://support.google.com/mail/answer/7126229):

> To avoid temporarily locking yourself out of your account, make sure you don't exceed 2500 MB per day for IMAP downloads and 500 MB per day for IMAP uploads. If you're setting up a single IMAP account on multiple computers, try taking a break between each setup.