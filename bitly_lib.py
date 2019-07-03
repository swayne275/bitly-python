#!/usr/bin/python3
import json                   # for json manipulation
import tornado.gen            # for async http gets to Bitly API
import tornado.httpclient     # for async http client
import tornado.httputil       # for various http client utilities
import urllib.parse           # for bitly url encoding
from datetime import datetime # for log message timing

##### Define convenience variables #####
html_prefix_end = '://' # delimiter between url scheme and domain
num_days = 30           # number of days to average over for this problem

async def async_get_group_guid(token):
    """ Async get the 'default_group_guid' using the provided access token
    Params:
        token: Access token for Bitly API request
    Throws:
        ValueError if group_guid is missing
        TypeError if group_guid is the wrong data type
    Return:
        [string] default_group_guid for the provided access token
    """
    response = await async_http_get(get_user_url(), token)
    if 'default_group_guid' not in response:
        log("Missing guid data from Bitly: " + json.dumps(response))
        raise ValueError('"default_group_guid" not in data retrieved from Bitly')
    if not isinstance(response['default_group_guid'], str):
        log("Invalid guid data type from Bitly: " + json.dumps(response))
        raise TypeError('"default_group_guid" from Bitly has invalid type')
    return response['default_group_guid']

async def async_get_bitlinks(token, group_guid):
    """ Async get and store all bitlinks for a provided group_guid
    Params:
        token: Access token for Bitly API request
        group_guid: group_guid to get the bitlinks for
    Return:
        List of encoded domain/hashes for the bitlinks for this group_guid
    """
    response = await async_http_get(get_bitlinks_url(group_guid), token)
    validate_bitlinks_response(response)
    encoded_bitlinks_list = []
    for link_obj in response['links']:
        bitlink_domain_hash = parse_bitlink(link_obj['link'])
        encoded_bitlink = urllib.parse.quote(bitlink_domain_hash)
        encoded_bitlinks_list.append(encoded_bitlink)
    return encoded_bitlinks_list

def validate_bitlinks_response(response):
    """ Validate the Bitly data returned containing bitlinks for a group_guid
    Params:
        response: JSON data from Bitly containing bitlinks for a group_guid
    Throws:
        ValueError if expected field is missing
        TypeError if 'link' field is the wrong type
    """
    if 'links' not in response:
        raise ValueError('"links" field not in data retrieved from Bitly')
    for link_obj in response['links']:
        if 'link' not in link_obj:
            log('"link" field missing from bitlinks data: ' + json.dumps(link_obj))
            raise ValueError('"link" field not in data retrieved from Bitly')
        if not isinstance(link_obj['link'], str):
            raise TypeError('"link" field data type from Bitly is incorrect')

async def async_get_country_counts(token, encoded_bitlinks_list):
    """ Async get country click metrics, per bitlink, per month
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
        response = await async_http_get(get_country_url(encoded_bitlink), token, params=payload)
        validate_country_response(response)
        for country_obj in response['metrics']:
            country_str = country_obj['value']
            country_clicks = country_obj['clicks']
            bitlinks_data[encoded_bitlink] = {}
            bitlinks_data[encoded_bitlink][country_str] = (country_clicks / num_days)
    return bitlinks_data

def validate_country_response(response):
    """ Validate the Bitly data returned containing metrics for a bitlink
    Params:
        response: JSON data from Bitly containing bitlinks for a group_guid
    Throws:
        ValueError if expected field is missing
    """
    if 'metrics' not in response:
        raise ValueError('"metrics" field not in data retrieved from Bitly')
    for country_obj in response['metrics']:
        if 'value' not in country_obj:
            log('"value" field missing from bitlinks data: ' + json.dumps(country_obj))
            raise ValueError('"value" field not in data retrieved from Bitly')
        if 'clicks' not in country_obj:
            log('"clicks" field missing from bitlinks data: ' + json.dumps(country_obj))
            raise ValueError('"clicks" field not in data retrieved from Bitly')

@tornado.gen.coroutine
def async_http_get(base_url, token, params={}):
    """ Non-blocking HTTP get for use with an Authorization: Bearer access token
    Note: Expects JSON response from {url}
    Params:
        base_url: URL to HTTP Get data from (no query parameters)
        token: Access token for Bitly API request
        params: [optional] query parameters for the HTTP request
    Throws:
        tornado.httpclient.HTTPError if Bitly response status is not 200
    Return:
        JSON data resulting from the HTTP get
    """
    client = tornado.httpclient.AsyncHTTPClient()
    headers = tornado.httputil.HTTPHeaders({"Authorization": "Bearer " + token})
    url = tornado.httputil.url_concat(base_url, params)
    request = tornado.httpclient.HTTPRequest(url, method='GET', headers=headers)

    response = yield client.fetch(request)
    json_body = {}
    try:
        json_body = json.loads(response.body)
    except Exception as e:
        # In general don't catch generic, but functionally it doesn't matter
        # why the JSON couldn't parse, just that it couldn't parse. Would not
        # do in production
        log("Could not parse data from Bitly (expected JSON): " + str(e))

    raise tornado.gen.Return(json_body)

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

def log(log_msg):
    """ Standardized way to log a bitly_lib message (read: output to console)
    Params:
        log_msg: Message to log, ideally human-readable
    """
    log_data = "[" + str(datetime.now()) + "] bitly_lib: %s" % log_msg
    print(log_data)