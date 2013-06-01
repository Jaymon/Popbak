# Popbak

Popbak is a Python script that will back up an email account (any email account that supports POP access) into a local folder. Attachments will also be backed up with the message in plaintext (.txt files).

I wrote this because I like having a plain text copy of my email, I don't want an mbox backup or anything like that, I want
an easy way to read the email and see the attachments.

## Example

I don't think I describe what this does very well, so here's an example, let's say you have 2 emails in your email inbox:

    foo@bar.com "this is my title"
    baz@foo.com "there is a jpg and a pdf file in this email"

Now, if you run this script, it will backup the emails like this:

    bakupdir/
      foo@bar.com/
        this is the title.txt
      baz@foo.com/
        there is a jpg and a pdf file in this email/
          attachment.jpg
          attachment.pdf
          there is a jpg and a pdf file in this email.txt

## How to run from the commandline

    $ python popbak.py -u USERNAME -p PASSWORD -s SERVER -o PORT -d "/path/to/backupdir"

To see all options:

    $ python popbak.py --help

### Back up your gmail account

    $ python popbak.py -u example@gmail.com -p PASSWORD -s pop.gmail.com -o 995 -d "/path/to/backupdir"

Make sure you have [activated pop access on your gmail account](http://mail.google.com/support/bin/answer.py?answer=13273&topic=12890).

## Installation

You only really need the `popbak.py` module and Python 2.7ish, so you can just grab the `popbak.py` file and run it. 

You could also install using git:

    $ git clone git@github.com:Jaymon/Popbak.git install/dir

## Todo

1 - it should detect html in the headers and set the extension to `.html` instead of `.txt`

2 - I don't think it is handling writing out unicode very well

3 - I should add a setup.py file so it can be installed with Pip and also so it will be available globally at `popbak`

## License

MIT, do with this as you please, I'd love pull requests if you fix problems or make it better.

