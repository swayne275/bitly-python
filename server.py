#!/usr/bin/python3
from datetime import datetime
import signal
import sys
import json
import tornado.ioloop
import tornado.web # !!! SW requirement
# for http requests
import requests
# for url encoding
import urllib.parse

##### Define basic error types #####
generic_internal_err = 1 # generic internal error
unimplemented_err    = 2 # route or method was not implemented
invalid_data         = 3 # expected data was not present

access_token = 'cb1da22a1c837ba3f8cd54781461397472cce43e'
user_url = 'https://api-ssl.bitly.com/v4/user'
group_guid = 'Bj71ifpGx2i'
num_days = 30 # number of days for this problem
bitlinks_list = []

api_version = "v0.1"

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        try:
            response = {}
            response['apiversion'] = api_version
            send_success(self, response)
        except Exception as e:
            log('Error: could not serve /: ' + str(e))

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
            populate_bitlinks()
            response = {}
            response['sampledata'] = 'hello world'
            response['bitlinks'] = bitlinks_list
            send_success(self, response)
        except Exception as e:
            log("Error: could not handle clicks! " + str(e))

def get_group_guid():
    data = http_get(user_url)
    if 'default_group_guid' not in data:
        raise ValueError('default_group_guid not retrieved from Bitly')
    if not isinstance(data['default_group_guid'], str):
        raise ValueError('default_group_guid type is invalid from Bitly')
    return data['default_group_guid']

def populate_bitlinks():
    data = http_get(get_bitlinks_url())
    if 'links' not in data:
        raise ValueError('"links" field not in data retrieved from Bitly')
    for link_obj in data['links']:
        if 'link' not in link_obj:
            raise ValueError('"link" field not in data retrieved from Bitly: ' + json.dumps(link_obj))
        if not isinstance(link_obj['link'], str):
            raise ValueError('"link" field data type from Bitly is incorrect')
        encoded_url = urllib.parse.quote(link_obj['link'])
        bitlinks_list.append(encoded_url)

def http_get(url):
    headers = {"Authorization": "Bearer " + access_token}
    r = requests.get(url=url, headers=headers)
    data = r.json()
    return data

def handle_unimplemented(request_handler):
    """ Deal with routes and methods that aren't implemented
    """
    try:
        send_httperr(request_handler, unimplemented_err, "Not implemented", status=501)
    except Exception as e:
        log("Error: Could not respond to unimplemented route/method: " + str(e))

def send_success(calling_handler, json_body):
    try:
        calling_handler.set_header('Content-Type', 'application/json')
        json_body['uri'] = calling_handler.request.uri
    except Exception as e:
        send_httperr(calling_handler, generic_internal_err,
            "Error making success response: " + str(e))
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
    log("Caught signal, exiting...")
    sys.exit(0)

def server_init():
    log("API version %s running..." % api_version)
    # install signal handler
    signal.signal(signal.SIGINT, signal_handler)

def set_access_token(token):
    global access_token
    # verify string and length
    access_token = token

def set_group_guid():
    global group_guid
    group_guid = get_group_guid()

def get_bitlinks_url():
    return ('https://api-ssl.bitly.com/v4/groups/%s/bitlinks' % group_guid)

def get_countries_url(bitlink):
    return ('https://api-ssl.bitly.com/v4/bitlinks/%s/countries' % bitlink)

def make_app():
    return tornado.web.Application([
        ("/", MainHandler),
        ("/api/%s/get-clicks/?" % api_version, ClickHandler),
        ("/.*", GenericHandler)
    ])

if __name__ == "__main__":
    try:
        # maybe grab info first?
        # verify type, length of access_token
        set_access_token('cb1da22a1c837ba3f8cd54781461397472cce43e')
        # verify can get group_guid and type
        set_group_guid()
        server_init()
        # Start the http webserver
        app = make_app()
        app.listen(8080)
        log("started http server on port 8080")
        tornado.ioloop.IOLoop.current().start()
    except Exception as e:
        log("Could not start API on port 8080: " +str(e))