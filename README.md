# Popbak

Popbak is a Python script that will back up an email account (any email account that supports POP access) into a local folder.

I wrote this because I like having an archival copy of my email, I don't want an mbox backup or anything like that, I want an easy way to read the email and see the attachments.

I don't think I described what Popbak does very well, so here's an example, let's say you have 2 emails in your email inbox:

    foo@bar.com "this is my title"
    baz@foo.com "there is a jpg and a pdf file in this email"

Now, if you run Popbak, it will backup the emails like this:

    bakupdir/
      bar.com/
        foo@bar.com/
          this is the title.txt/
            body 1.txt
      foo.com/
        baz@foo.com/
          there is a jpg and a pdf file in this email/
            attachment.jpg
            attachment.pdf
            body 1.txt


## How to run from the command line

    $ python popbak.py -u USERNAME -p PASSWORD -s SERVER -o PORT -d "/path/to/backupdir"

To see all options:

    $ python popbak.py --help


### Back up your gmail account

    $ python popbak.py -u example@gmail.com -p PASSWORD -s pop.gmail.com -o 995 -d "/path/to/backupdir"

Make sure you have [activated pop access on your gmail account](http://mail.google.com/support/bin/answer.py?answer=13273&topic=12890). You might have to [create an app password for Popbak](https://support.google.com/accounts/answer/185833) in your [Google account security settings](https://myaccount.google.com/).

## Installation

Clone this repo:

    $ git clone git@github.com:Jaymon/Popbak.git <DIRECTORY>


Install the dependencies:

    $ cd <DIRECTORY>
    $ pip install -r requirements.txt

Then go ahead and run Popbak using Python 3.7+:

    $ python popbak.py --help
    
