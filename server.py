#!/usr/bin/python3
from datetime import datetime # for log message timing
import signal                 # for signal handling
import sys                    # for signal handling
import json                   # for JSON manipulation
import tornado.ioloop         # for web server hosting
import tornado.web            # for web server hosting
import tornado.gen            # for making web server async
import tornado.httpclient
import requests               # for http requests
import urllib.parse           # for bitly url encoding

##### Define port for web server to listen on #####
web_server_port = 8080

##### Define basic error types #####
generic_internal_err = 1 # generic internal error
bitly_api_data_err   = 2 # Bitly data was not formatted as expected
bitly_api_http_err   = 3 # Bitly API gave an HTTP error
bad_token_err        = 4 # User provided an invalid access_token

##### Define convenience variables #####
html_prefix_end = '://'
num_days = 30     # number of days to average over for this problem
api_version = "v0.1"

class MainHandler(tornado.web.RequestHandler):
    """ Handle gets for '/' by returning basic API data
    """
    @tornado.gen.coroutine
    def get(self):
        try:
            response = {}
            response['apiversion'] = api_version
            response['apidocumentation'] = 'In production I would give a doc link'
            send_success(self, response)
        except Exception as e:
            log('Error: could not serve /: ' + str(e))

    @tornado.gen.coroutine
    def write_error(self, status_code, **kwargs):
        """ See override_write_error for details
        """
        override_write_error(self, status_code)

class ClickHandler(tornado.web.RequestHandler):
    """ Handle gets for the main endpoint !!! SW fill in and return bitlinks country metrics
    """
    @tornado.gen.coroutine
    def get(self):
        try:
            token = get_access_token(self)
            if not token:
                send_httperr(self, bad_token_err, "Invalid access token provided",
                    status=401)
                return
            group_guid = yield async_get_group_guid(token)
            encoded_bitlinks_list = yield async_get_bitlinks(token, group_guid)
            bitlinks_data = yield async_get_country_counts(token, encoded_bitlinks_list)

            response = {}
            response['metrics'] = bitlinks_data
            send_success(self, response)
        except ValueError as value_error:
            send_httperr(self, bitly_api_data_err, str(value_error))
        except tornado.httpclient.HTTPError as http_err:
            log("Bitly API raised an HTTP error: " + str(http_err))
            send_httperr(self, bitly_api_http_err, str(http_err))
        except Exception as e:
            log("Exception type: " + type(e).__name__)
            log("Error: could not handle clicks! " + str(e))

    @tornado.gen.coroutine
    def write_error(self, status_code, **kwargs):
        """ See override_write_error for details
        """
        override_write_error(self, status_code)

class GenericHandler(tornado.web.RequestHandler):
    """ Handle all unspecified endpoints by returning a pretty JSON error
    """
    @tornado.gen.coroutine
    def write_error(self, status_code, **kwargs):
        """ See override_write_error for details
        """
        override_write_error(self, status_code)

##### Web server utilities #####

def override_write_error(request_handler, status_code):
    """ Override the default tornado write_error to return pretty JSON
    Params:
        request_handler: Tornado API endpoint handler implementing this
        status_code: HTML status code
    """
    request_handler.set_header('Content-Type', 'application/json')
    request_handler.finish(json.dumps({
            'error': {
                'code': status_code,
                'message': request_handler._reason,
            }
        }))

def send_success(request_handler, json_body):
    """ Handle boilerplate for returning HTTP 200 with data
    Params:
        calling_handler: Tornado API endpoint sending success + data
        json_body: JSON data to send to the client
    """
    try:
        request_handler.set_header('Content-Type', 'application/json')
        json_body['uri'] = request_handler.request.uri
    except Exception as e:
        send_httperr(request_handler, generic_internal_err,
            "Error making success response: " + str(e))
    else:
        request_handler.write(json_body)

def send_httperr(request_handler, err_type, err_msg, status=500):
    """ Handle boilerplate for returning HTTP error with message
    Params
        calling_handler: Tornado API endpoint returning error
        err_type: Type enum for automations to better understand
        err_msg: Human-readable semi-specific error message
        status: [optional] HTTP code to send error as
    """
    uri = request_handler.request.uri
    log("Sending HTTP error (for uri %s): %s" % (uri, err_msg))
    request_handler.set_header('Content-Type', 'application/json')
    http_err = {}
    http_err['errortype'] = err_type
    http_err['errormessage'] = err_msg
    http_err['uri'] = uri
    request_handler.set_status(status)
    request_handler.finish(http_err)

def log(log_msg):
    """ Standardized way to log a message (read: output to console)
    Params:
        log_msg: Message to log, ideally human-readable
    """
    log_data = "[" + str(datetime.now()) + "] %s" % log_msg
    print(log_data)

def signal_handler(signal, frame):
    """ Install signal handler for things like Ctrl+C
    """
    log("Caught signal, exiting...")
    sys.exit(0)

def server_init():
    """ Perform pre-app init tasks before initializing the web server
    """
    log("Initializing Bitly Backend Test API web server")
    signal.signal(signal.SIGINT, signal_handler)

def make_app():
    """ Set up the tornado web server handlers
    Return:
        Tornado web app to run
    """
    return tornado.web.Application([
        ("/", MainHandler),
        ("/api/%s/get-clicks/?" % api_version, ClickHandler),
        ("/.*", GenericHandler)
    ])

##### Bitly API Utilities #####

def get_access_token(request_handler):
    """ Get the access token from the client's request
    Params:
        request_handler: Tornado API endpoint handler implementing this
    Return:
        String access token if 'valid', else None
    """
    token = request_handler.request.headers.get('access_token')
    if not isinstance(token, str):
        return None
    if not token:
        # strings are "falsy"
        return None
    return token

async def async_get_group_guid(token):
    response = await async_http_get(get_user_url(), token)
    if 'default_group_guid' not in response:
        log("Missing guid data from Bitly: " + json.dumps(response))
        raise ValueError('"default_group_guid" not in data retrieved from Bitly')
    if not isinstance(response['default_group_guid'], str):
        log("Invalid guid data type from Bitly: " + json.dumps(response))
        raise ValueError('"default_group_guid" from Bitly has invalid type')
    return response['default_group_guid']

def get_group_guid(token):
    """ Get the 'default_group_guid' using the provided access token
    Params:
        token: Access token for Bitly API request
    Return:
        [string] default_group_guid for the provided access token
    """
    data = http_get(get_user_url(), token)
    if 'default_group_guid' not in data:
        log("Missing guid data from Bitly: " + json.dumps(data))
        raise ValueError('"default_group_guid" not in data retrieved from Bitly')
    if not isinstance(data['default_group_guid'], str):
        log("Invalid guid data type from Bitly: " + json.dumps(data))
        raise ValueError('"default_group_guid" from Bitly has invalid type')
    return data['default_group_guid']

async def async_get_bitlinks(token, group_guid):
    """ Get and store all bitlinks for a provided group_guid
    Params:
        token: Access token for Bitly API request
        group_guid: group_guid to get the bitlinks for
    Return:
        List of encoded domain/hashes for the bitlinks for this group_guid
    """
    response = await async_http_get(get_bitlinks_url(group_guid), token)
    validate_bitlinks_data(response)
    encoded_bitlinks_list = []
    for link_obj in response['links']:
        bitlink_domain_hash = parse_bitlink(link_obj['link'])
        encoded_bitlink = urllib.parse.quote(bitlink_domain_hash)
        encoded_bitlinks_list.append(encoded_bitlink)
    return encoded_bitlinks_list

def get_bitlinks(token, group_guid):
    """ Get and store all bitlinks for a provided group_guid
    Params:
        token: Access token for Bitly API request
        group_guid: group_guid to get the bitlinks for
    Return:
        List of encoded domain/hashes for the bitlinks for this group_guid
    """
    data = http_get(get_bitlinks_url(group_guid), token)
    validate_bitlinks_data(data)
    encoded_bitlinks_list = []
    for link_obj in data['links']:
        bitlink_domain_hash = parse_bitlink(link_obj['link'])
        encoded_bitlink = urllib.parse.quote(bitlink_domain_hash)
        encoded_bitlinks_list.append(encoded_bitlink)
    return encoded_bitlinks_list

def validate_bitlinks_data(data):
    """ Validate the Bitly data returned containing bitlinks for a group_guid
    Params:
        data: JSON data from Bitly containing bitlinks for a group_guid
    """
    if 'links' not in data:
        raise ValueError('"links" field not in data retrieved from Bitly')
    for link_obj in data['links']:
        if 'link' not in link_obj:
            log('"link" field missing from bitlinks data: ' + json.dumps(link_obj))
            raise ValueError('"link" field not in data retrieved from Bitly')
        if not isinstance(link_obj['link'], str):
            raise ValueError('"link" field data type from Bitly is incorrect')

async def async_get_country_counts(token, encoded_bitlinks_list):
    """ Package country click metrics per Bitlink
    Params:
        token: Access token for Bitly API request
        encoded_bitlinks_list: List of encoded bitlinks to get metrics for
    Return:
        JSON data, organized by bitlink as follows:
        {
            "<bitlink1>": {
                "<country1>": float, <avg # clicks from <country1> over past 30 days>,
                ...
            },
            ...
        }
    """
    bitlinks_data = {}
    for encoded_bitlink in encoded_bitlinks_list:
        payload = {'unit': 'month'}
        data = await async_http_get(get_country_url(encoded_bitlink), token, params=payload)
        validate_country_data(data)
        for country_obj in data['metrics']:
            country_str = country_obj['value']
            country_clicks = country_obj['clicks']
            bitlinks_data[encoded_bitlink] = {}
            bitlinks_data[encoded_bitlink][country_str] = (country_clicks / num_days)
    return bitlinks_data

def get_country_counts(token, encoded_bitlinks_list):
    """ Package country click metrics per Bitlink
    Params:
        token: Access token for Bitly API request
        encoded_bitlinks_list: List of encoded bitlinks to get metrics for
    Return:
        JSON data, organized by bitlink as follows:
        {
            "<bitlink1>": {
                "<country1>": float, <avg # clicks from <country1> over past 30 days>,
                ...
            },
            ...
        }
    """
    bitlinks_data = {}
    for encoded_bitlink in encoded_bitlinks_list:
        payload = {'unit': 'month'}
        data = http_get(get_country_url(encoded_bitlink), token, params=payload)
        validate_country_data(data)
        for country_obj in data['metrics']:
            country_str = country_obj['value']
            country_clicks = country_obj['clicks']
            bitlinks_data[encoded_bitlink] = {}
            bitlinks_data[encoded_bitlink][country_str] = (country_clicks / num_days)
    return bitlinks_data

def validate_country_data(data):
    """ Validate the Bitly data returned containing metrics for a bitlink
    Params:
        data: JSON data from Bitly containing bitlinks for a group_guid
    """
    if 'metrics' not in data:
        raise ValueError('"metrics" field not in data retrieved from Bitly')
    for country_obj in data['metrics']:
        if 'value' not in country_obj:
            log('"value" field missing from bitlinks data: ' + json.dumps(country_obj))
            raise ValueError('"value" field not in data retrieved from Bitly')
        if 'clicks' not in country_obj:
            log('"clicks" field missing from bitlinks data: ' + json.dumps(country_obj))
            raise ValueError('"clicks" field not in data retrieved from Bitly')

@tornado.gen.coroutine
def async_http_get(base_url, token, params={}):
    """ HTTP get wrapper that handles the authorization header for the Bitly API
    Note: Expects JSON response from {url}
    Params:
        base_url: URL to HTTP Get data from (no query parameters)
        token: Access token for Bitly API request
        params: [optional] query parameters for the HTTP request
    Throws:
        requests.HTTPError if Bitly response status is not 200
    Return:
        JSON data resulting from the HTTP get
    """
    client = tornado.httpclient.AsyncHTTPClient()
    headers = tornado.httputil.HTTPHeaders({"Authorization": "Bearer " + token})
    url = tornado.httputil.url_concat(base_url, params)
    request = tornado.httpclient.HTTPRequest(url, method='GET', headers=headers)

    response = yield client.fetch(request)
    json_body = json.loads(response.body)
    raise tornado.gen.Return(json_body)

def http_get(url, token, params={}):
    """ HTTP get wrapper that handles the authorization header for the Bitly API
    Note: Expects JSON response from {url}
    Params:
        url: URL to HTTP Get data from
        token: Access token for Bitly API request
        params: [optional] query parameters for the HTTP request
    Throws:
        requests.HTTPError if Bitly response status is not 200
    Return:
        JSON data resulting from the HTTP get
    """
    headers = {"Authorization": "Bearer " + token}
    response = requests.get(url=url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()

def get_user_url():
    """ Return Bitly API endpoint for getting the group_guid
    """
    return 'https://api-ssl.bitly.com/v4/user'

def get_bitlinks_url(group_guid):
    """ Return Bitly API endpoint for accessing group_guid bitlinks
    Params:
        group_guid: group_guid to use to build this URL
    """
    return ('https://api-ssl.bitly.com/v4/groups/%s/bitlinks' % group_guid)

def get_country_url(bitlink):
    """ Return Bitly API endpoint for accessing bitly metrics by country
    """
    return ('https://api-ssl.bitly.com/v4/bitlinks/%s/countries' % bitlink)

def parse_bitlink(bitlink_url):
    """ Strip a URL of the HTML scheme and delimiter
    Params:
        bitlink_url: complete URL of the bitlink to strip
    Return:
        Domain and hash of the bitlink
    """
    prefix_start_pos = bitlink_url.find(html_prefix_end)
    # increment the counter the last char of the '{scheme}://' URL component
    prefix_end_pos = prefix_start_pos + len(html_prefix_end)
    # return the domain and hash of the bitlink
    return bitlink_url[prefix_end_pos:]

if __name__ == "__main__":
    try:
        log("Starting Bitly backend test API, version %s" % api_version)
        # verify can get group_guid and type
        server_init()
        # Start the http webserver
        app = make_app()
        app.listen(web_server_port)
        log("started http server on port %d" % web_server_port)
        tornado.ioloop.IOLoop.current().start()
    except Exception as e:
        log("Could not start API on port %d: %s" % (web_server_port, str(e)))