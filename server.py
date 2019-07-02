#!/usr/bin/python3
from datetime import datetime
import signal
import sys
import tornado.ioloop
import tornado.web # !!! SW requirement

##### Define basic error types #####
generic_internal_err = 1 # generic internal error
unimplemented_err    = 2 # route or method was not implemented

api_key = 'cb1da22a1c837ba3f8cd54781461397472cce43e'
first_url = 'https://api-ssl.bitly.com/v4/user'
api_version = "v0.1"

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        try:
            response = {}
            response['apiversion'] = api_version
            send_success(self, response)
        except Exception as e:
            log('Error: could not serve /: ' + e.message)

    def post(self):
        handle_unimplemented(self)

class GenericHandler(tornado.web.RequestHandler):
    """ Handler for unimplemented routes/methods to return a nice error
    """
    def get(self):
        handle_unimplemented(self)

    def post(self):
        handle_unimplemented(self)

class ClickHandler(tornado.web.RequestHandler):
    def get(self):
        try:
            response = {}
            response['sampledata'] = 'hello world'
            send_success(self, response)
        except Exception as e:
            log("Error: could not handle clicks! " + e.message)

def handle_unimplemented(request_handler):
    """ Deal with routes and methods that aren't implemented
    """
    try:
        send_httperr(request_handler, unimplemented_err, "Not implemented", status=501)
    except Exception as e:
        log("Error: Could not respond to unimplemented route/method: " + e.message)

def send_success(calling_handler, json_body):
    try:
        calling_handler.set_header('Content-Type', 'application/json')
        json_body['uri'] = calling_handler.request.uri
    except Exception as e:
        send_httperr(calling_handler, generic_internal_err,
            "Error making success response: " + e.message)
    else:
        calling_handler.write(json_body)

def send_httperr(calling_handler, err_type, err_msg, status=500):
    log("Sending HTTP error: " + err_msg)
    calling_handler.set_header('Content-Type', 'application/json')
    http_err = {}
    http_err['errortype'] = err_type
    http_err['errormessage'] = err_msg
    http_err['uri'] = calling_handler.request.uri
    calling_handler.set_status(status)
    calling_handler.finish(http_err)

def log(log_msg):
    log_data = "[" + str(datetime.now()) + "] %s" % log_msg
    print(log_data)
    # !!! SW add file logging possibly

def signal_handler(signal, frame):
    print ("Ctrl + C!")
    sys.exit(0)

def server_init():
    log("API version %s running..." % api_version)
    # install signal handler
    signal.signal(signal.SIGINT, signal_handler)

def make_app():
    return tornado.web.Application([
        ("/", MainHandler),
        ("/api/%s/get-clicks/?" % api_version, ClickHandler),
        ("/.*", GenericHandler)
    ])

if __name__ == "__main__":
    try:
        server_init()
        # Start the http webserver
        app = make_app()
        app.listen(8080)
        log("started http server on port 8080")
        tornado.ioloop.IOLoop.current().start()
    except Exception as e:
        log("Could not start API on port 8080: " + e.message)