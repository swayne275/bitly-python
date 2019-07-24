# Library for interacting with the relevant Bitly API endpoints
# as per the coding challenge specifications
#
# Stephen Wayne

import json                   # for json manipulation
import tornado.gen            # for async http gets to Bitly API
import tornado.httpclient     # for async http client
import tornado.httputil       # for various http client utilities
import urllib.parse           # for bitly url encoding
import logging
import time # !!! SW remove when done testing

##### Define convenience variables #####
html_prefix_end = '://' # delimiter between url scheme and domain
num_days = 30           # number of days to average over for this problem

@tornado.gen.coroutine
def async_get_metrics(token):
    """ Async get country click metrics for a user's default group
    Params:
        token: Access token for Bitly API request
    Return:
        JSON data with click metrics, organized by bitlink as follows:
        {
            "<bitlink1>": {
                "<country1>": float, <avg # clicks from <country1> over past 30 days>,
                ...
            },
            ...
        }
    """
    group_guid = yield async_get_group_guid(token)
    encoded_bitlinks_list = yield async_get_bitlinks(token, group_guid)
    bitlinks_data = yield async_get_country_counts(token, encoded_bitlinks_list)
    return bitlinks_data

@tornado.gen.coroutine
def async_get_group_guid(token):
    """ Async get the 'default_group_guid' using the provided access token
    Params:
        token: Access token for Bitly API request
    Throws:
        ValueError if group_guid is missing
        TypeError if group_guid is the wrong data type
    Return:
        [string] default_group_guid for the provided access token
    """
    response = yield async_http_get_json(get_user_url(), token)
    if 'default_group_guid' not in response:
        logging.error(f'Missing guid data from Bitly: {json.dumps(response)}')
        raise ValueError('"default_group_guid" not in data retrieved from Bitly')
    if not isinstance(response['default_group_guid'], str):
        logging.error(f'Invalid guid data type from Bitly: {json.dumps(response)}')
        raise TypeError('"default_group_guid" from Bitly has invalid type')
    raise tornado.gen.Return(response['default_group_guid'])

@tornado.gen.coroutine
def async_get_bitlinks(token, group_guid):
    """ Async get and store all bitlinks for a provided group_guid
    Params:
        token: Access token for Bitly API request
        group_guid: group_guid to get the bitlinks for
    Return:
        List of encoded domain/hashes for the bitlinks for this group_guid
    """
    response = yield async_http_get_json(get_bitlinks_url(group_guid), token)
    validate_bitlinks_response(response)
    encoded_bitlinks_list = []
    for link_obj in response['links']:
        bitlink_domain_hash = parse_bitlink(link_obj['link'])
        encoded_bitlink = urllib.parse.quote(bitlink_domain_hash)
        encoded_bitlinks_list.append(encoded_bitlink)
    raise tornado.gen.Return(encoded_bitlinks_list)

@tornado.gen.coroutine
def async_get_country_counts(token, encoded_bitlinks_list):
    """ Async/concurrently get country click metrics, per bitlink, per month
    Params:
        token: Access token for Bitly API request
        encoded_bitlinks_list: List of encoded bitlinks to get metrics for
    Return:
        JSON data with click metrics, organized by bitlink as follows:
        {
            "<bitlink1>": {
                "<country1>": float, <avg # clicks from <country1> over past 30 days>,
                ...
            },
            ...
        }
    """
    bitlinks_data = {}
    payload = {'unit': 'day', 'units': 30}
    responses = yield tornado.gen.multi([async_http_get(get_country_url(url), token, params=payload)
        for url in encoded_bitlinks_list])

    # tornado multi produces a list in the same order as passed in, so we can zip the
    # encoded bitlinks (as keys) with the response futures (as values) safely
    bitlink_to_country_future = dict(zip(encoded_bitlinks_list, responses))
    for encoded_bitlink, country_future in bitlink_to_country_future.items():
        json_country_data = {}
        try:
            json_country_data = json.loads(country_future.body)
        except Exception as e:
            # In general don't catch generic, but functionally it doesn't matter
            # why the JSON couldn't parse, just that it couldn't parse. Would not
            # do in production
            logging.error(f'Could not parse data from Bitly for bitlink {encoded_bitlink}: {country_future}')

        validate_country_response(json_country_data)
        bitlinks_data[encoded_bitlink] = {}
        for country_obj in json_country_data['metrics']:
            country_name = country_obj['value']
            country_clicks = country_obj['clicks']
            bitlinks_data[encoded_bitlink][country_name] = (country_clicks / num_days)

    raise tornado.gen.Return(bitlinks_data)

@tornado.gen.coroutine
def async_http_get_json(base_url, token, params=None):
    """ Non-blocking HTTP get for use with an Authorization: Bearer access token
    Note: Expects JSON response from {base_url}
    Params:
        base_url: URL to HTTP Get data from (no query parameters)
        token: Access token for Bitly API request
        params: [optional] query parameters for the HTTP request as dictionary
    Throws:
        tornado.httpclient.HTTPError if Bitly response status is not 200
    Return:
        JSON data resulting from the HTTP get
    """
    response = yield async_http_get(base_url, token, params=params)
    json_body = {}
    try:
        json_body = json.loads(response.body)
    except Exception as e:
        # In general don't catch generic, but functionally it doesn't matter
        # why the JSON couldn't parse, just that it couldn't parse. Would not
        # do in production
        logging.error(f'Could not parse data from Bitly (expected JSON): {str(e)}')

    raise tornado.gen.Return(json_body)

@tornado.gen.coroutine
def async_http_get(base_url, token, params=None):
    """ Non-blocking HTTP get for use with an Authorization: Bearer access token
    Params:
        base_url: URL to HTTP Get data from (no query parameters)
        token: Access token for Bitly API request
        params: [optional] query parameters for the HTTP request as dictionary
    Throws:
        tornado.httpclient.HTTPError if Bitly response status is not 200
    Return:
        Response future resulting from HTTP get
    """
    print(f"!!! SW url {base_url} at time {time.time()}")
    client = tornado.httpclient.AsyncHTTPClient()
    headers = tornado.httputil.HTTPHeaders({"Authorization": "Bearer " + token})
    url = tornado.httputil.url_concat(base_url, params)
    request = tornado.httpclient.HTTPRequest(url, method='GET', headers=headers)
    response = yield client.fetch(request)

    raise tornado.gen.Return(response)

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
            logging.error(f'"link" field missing from bitlinks data: {json.dumps(link_obj)}')
            raise ValueError('"link" field not in data retrieved from Bitly')
        if not isinstance(link_obj['link'], str):
            raise TypeError('"link" field data type from Bitly is incorrect')

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
            logging.error(f'"value" field missing from bitlinks data: {json.dumps(country_obj)}')
            raise ValueError('"value" field not in data retrieved from Bitly')
        if 'clicks' not in country_obj:
            logging.error(f'"clicks" field missing from bitlinks data: {json.dumps(country_obj)}')
            raise ValueError('"clicks" field not in data retrieved from Bitly')

def get_user_url():
    """ Return Bitly API endpoint for getting the group_guid
    """
    return 'https://api-ssl.bitly.com/v4/user'

def get_bitlinks_url(group_guid):
    """ Return Bitly API endpoint for accessing group_guid bitlinks
    Params:
        group_guid: group_guid to use to build this URL
    """
    return (f'https://api-ssl.bitly.com/v4/groups/{group_guid}/bitlinks')

def get_country_url(bitlink):
    """ Return Bitly API endpoint for accessing bitly metrics by country
    """
    return (f'https://api-ssl.bitly.com/v4/bitlinks/{bitlink}/countries')

def parse_bitlink(bitlink_url):
    """ Strip a URL of the HTML scheme and delimiter
    !!! SW TODO prefix_start_pos == -1 if not found, handle that case
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
