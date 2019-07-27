#!/usr/bin/env python3

"""
Web server to host the API that meets the requirements of the
Bitly backend coding challenge

Once you have the requirements installed for Python 3
(tornado and urllib), cd to this directory and run
"python3 server.py" to start the webserver

Stephen Wayne
"""

import signal                 # for signal handling
import sys                    # for signal handling
import json                   # for JSON manipulation
import logging
from enum import Enum         # for standard error enumeration
from http import HTTPStatus   # for http status enum (for code clarity)
import tornado.ioloop         # for web server hosting
import tornado.web            # for web server hosting
import tornado.httpclient     # for HTTP exceptions from tornado AsyncHTTPClient
import bitly_lib as bitly     # for bitly api interactions

##### Define port for web server to listen on #####
WEB_SERVER_PORT = 8080

##### Define basic error types #####
class Errors(Enum):
    """ Enumeration of standardized errors to return to client
    """
    GENERIC_INTERNAL_ERR = 1    # generic internal error
    BITLY_API_DATA_ERR = 2      # Bitly data was not formatted as expected
    BITLY_API_HTTP_ERR = 3      # Bitly API gave an HTTP error
    BAD_TOKEN_ERR = 4           # User provided an invalid access_token

##### Define convenience variables #####
API_VERSION = "v1"      # api version served by this file

class MainHandler(tornado.web.RequestHandler):
    """ Handle gets for '/' by returning basic API data
    """
    async def get(self):
        try:
            response = {}
            response['apiversion'] = API_VERSION
            response['apidocumentation'] = 'In production I would give a doc link'
            send_success(self, response)
        except Exception as generic_e:
            logging.error('Error: could not serve /: %s', str(generic_e))

    async def write_error(self, status_code, **kwargs):
        """ See override_write_error for details
        """
        override_write_error(self, status_code)

class ClickHandler(tornado.web.RequestHandler):
    """ Handle "/api/<ver>/metrics" and return bitlinks country metrics
    Note: An optional "country" filter will provide results for only the
          string specified (compared as lowercase)
    """
    async def get(self):
        try:
            token = self.request.headers.get('access_token')
            if not token or not isinstance(token, str):
                send_httperr(self, Errors.BAD_TOKEN_ERR.value, "Invalid access token provided",
                             status=HTTPStatus.UNAUTHORIZED)
                return

            country_filter_str = self.get_argument("country", default=None)
            bitlinks_data = await bitly.async_get_metrics(token,
                                                          country=country_filter_str)

            response = {}
            response['metrics'] = bitlinks_data
            send_success(self, response)
        except ValueError as value_error:
            send_httperr(self, Errors.BITLY_API_DATA_ERR.value, str(value_error))
        except TypeError as type_error:
            send_httperr(self, Errors.BITLY_API_DATA_ERR.value, str(type_error))
        except tornado.httpclient.HTTPError as http_err:
            logging.error('Bitly API raised an HTTP error: %s', str(http_err))
            send_httperr(self, Errors.BITLY_API_HTTP_ERR.value, str(http_err))
        except Exception as generic_e:
            logging.error('Error: could not handle clicks: %s', str(generic_e))

    async def write_error(self, status_code, **kwargs):
        """ See override_write_error for details
        """
        override_write_error(self, status_code)

class GenericHandler(tornado.web.RequestHandler):
    """ Handle all unspecified endpoints by returning a pretty JSON error
    """
    async def write_error(self, status_code, **kwargs):
        """ See override_write_error for details
        """
        override_write_error(self, status_code)

##### Web server utilities #####

def override_write_error(request_handler, status_code):
    """ Override the default tornado write_error to return pretty JSON
    Params:
        request_handler: Tornado API endpoint handler implementing this
        status_code: HTTP status code
    """
    request_handler.set_header('Content-Type', 'application/json')
    request_handler.finish(json.dumps({
        'error': {
            'code': status_code,
            'message': request_handler._reason,
        }
    }))

def send_success(request_handler, json_body):
    """
    Handle boilerplate for returning HTTP 200 with data
    :param request_handler: Tornado API endpoint sending success + data
    :param json_body: JSON data to send to the client
    """
    try:
        request_handler.set_header('Content-Type', 'application/json')
        json_body['uri'] = request_handler.request.uri
    except Exception as generic_e:
        send_httperr(request_handler, Errors.GENERIC_INTERNAL_ERR.value,
                     "Error making success response: " + str(generic_e))
    else:
        request_handler.write(json_body)

def send_httperr(request_handler, err_type, err_msg, status=HTTPStatus.INTERNAL_SERVER_ERROR):
    """
    Handle boilerplate for returning HTTP error with message
    :param request_handler: Tornado API endpoint returning error
    :param err_type: Type enum for automations to better understand
    :param err_msg: Human-readable semi-specific error message
    :param status: [optional] HTTPStatus enum to send error as
    """
    uri = request_handler.request.uri
    logging.debug('Sending HTTP error (for uri %s): %s', uri, err_msg)
    request_handler.set_header('Content-Type', 'application/json')
    http_err = {}
    http_err['errortype'] = err_type
    http_err['errormessage'] = err_msg
    http_err['uri'] = uri
    request_handler.set_status(status)
    request_handler.finish(http_err)

def signal_handler(_sig, _frame):
    """ Install signal handler for things like Ctrl+C
    """
    logging.info('Caught signal, exiting...')
    sys.exit(0)

def server_init():
    """ Perform pre-app init tasks before initializing the web server
    """
    logging.info('Initializing Bitly Backend Test API web server')
    signal.signal(signal.SIGINT, signal_handler)

def make_app():
    """ Set up the tornado web server handlers
    Return:
        Tornado web app to run
    """
    return tornado.web.Application([
        ('/', MainHandler),
        (f'/api/{API_VERSION}/metrics/?', ClickHandler),
        ('/.*', GenericHandler)
    ])

if __name__ == "__main__":
    try:
        logging.basicConfig(level=logging.INFO)
        logging.info('Starting Bitly backend test API, version %s', API_VERSION)
        # verify can get group_guid and type
        server_init()
        # Start the http webserver
        APP = make_app()
        APP.listen(WEB_SERVER_PORT)
        logging.info('Started http server on port %s', WEB_SERVER_PORT)
        tornado.ioloop.IOLoop.current().start()
    except Exception as generic_e:
        logging.critical('Could not start API on port %s: %s', WEB_SERVER_PORT, str(generic_e))
