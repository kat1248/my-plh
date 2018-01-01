#!/usr/bin/python
from werkzeug.contrib.profiler import ProfilerMiddleware
from application import application

application.config['PROFILE'] = True
application.wsgi_app = ProfilerMiddleware(application.wsgi_app, restrictions=[30])
application.run(debug=True)