# Signal Cartel's Little Helper

## Purpose

This is a utility for Eve Online, it looks up a list of characters and presents threat data. 
I have been a user of [Pirate's Little Helper](eve-plh.com) for awhile and this is
intended to replace that service for the Eve corporation, [Signal Cartel](http://www.eve-scout.com/signal-cartel/).

## Requirements

The server code is written in Python 2.7 using Flask.  The client side
code is Javascript with DataTables.  The information is pulled from
CCP using the ESI interface and zkillboard using their API.

## Running locally

1. Install a python virtual environment using virtualenv and install the requirements

```
$ virtualenv plh-env
$ source plh-env/bin/activate
$ pip install -r requirements.txt
```

2. Copy `config.dist` to `config.py` and modify to fit your environment

3. Start the server

```
$ python application.py
```

## Installing on a Linux Host

This assumes you have apache installed on your Linux host.

1. Clone this repository to your home directory

2. Install pip and requirements

```
$ sudo apt-get install python-pip
$ sudo -H pip install -r requirements.txt
```
3. Link the app directory to the site root

```
$ sudo ln -sT ~/flaskapp /var/www/html/my-plh
```
4. Enable mod_wsgi by editing `/etc/apache2/apache2.conf` and adding

```
WSGIDaemonProcess flaskapp threads=5
WSGIScriptAlias / /var/www/html/my-plh/my-plh.wsgi

<Directory my-plh>
    WSGIProcessGroup my-plh
    WSGIApplicationGroup %{GLOBAL}
    Order deny,allow
    Allow from all
</Directory>
```
5. Restart the webserver

```
$ sudo apachectl restart
```

## References

1. [ZKillboard API](https://github.com/zKillboard/zKillboard/wiki/API-(Statistics))
2. [CCP ESI API](https://esi.tech.ccp.is/latest/)
3. [Pirate's Little Helper](eve-plh.com)
4. [Javascript DataTables](https://datatables.net/)
