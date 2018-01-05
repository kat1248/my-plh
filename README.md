# my-plh

## Purpose

I have been a user of Pirate's Little Helper for awhile. This is
intended to replace that service.

## Requirements

The server code is writte in Python 2.7 using Flask.

## Run locally

1 Install a python virtual environment using virtualenv and install the requirements

```virtualenv plh-env
source plh-env/bin/activate
pip install -r requirements.txt
```

2 copy `config.dist` to `config.py` and modify to fit your environment

3 Start the server

```python application.py```
