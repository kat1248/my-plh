# -*- encoding: utf-8 -*-
import datetime

# -----------------------------------------------------
# Application configurations
# ------------------------------------------------------
DEBUG = True
SECRET_KEY = 'YouNeedToChangeThisToBeSecure!'
PORT = 5015
HOST = 'localhost'
MAX_CHARS = 30

# -----------------------------------------------------
# ESI Configs
# -----------------------------------------------------
ESI_DATASOURCE = 'tranquility'  # Change it to 'singularity' to use the test server
ESI_SWAGGER_JSON = 'https://esi.tech.ccp.is/latest/swagger.json?datasource=%s' % ESI_DATASOURCE
ESI_SECRET_KEY = 'VNZguWWs46g3iSQ7o735HUsuQYLmhPvR8F2pMn2h'  # your secret key
ESI_CLIENT_ID = 'd81053d71ead41509d564c1a69bdb4ca'  # your client ID
ESI_CALLBACK = 'http://%s:%d/sso/callback' % (HOST, PORT)  # the callback URI you gave CCP
ESI_USER_AGENT = 'kat1248@gmail.com for Signal Cartel Little Helper'
