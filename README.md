# bitly-python
Python solution to Bitly's backend coding challenge:
https://gist.github.com/jctbitly/05044bb3281ca6723bc118babc77afc7

# Summary
This is a solution to the bitly_backend_test, written in Python 3 using
Tornado as the primary library to both serve the API and interact with
the relevant Bitly API endpoints. The goal is to provide a reasonably
performant API that exposes the average number of daily clicks Bitlinks
in the user's default group received from each country over the last 30 days.

# Design Decisions
I chose Python and Tornado because I have already written a reasonably
performant API using these technologies for my previous work/projects,
and I was limited on how much time I could dedicate to this project. That
previous work, however, did not interact with another REST API, and was
mostly synchronous. I also knew that Tornado could host static assets in case
I ever wanted to build a simple GUI to interact with the Bitly API. Tornado
is also built to be async, which I knew I might want for API performance with
simultaneous requests.

I originally used the `response` Python library to synchronously interact
with the Bitly API, but later transitioned to use Tornado's AsyncHTTPClient.
Since this project is inherently IO bound (most of the time is spent
waiting on Bitly's API) it made sense to build this as an async API so
that multiple clients could use it simultaneously without serially
waiting on Bitly API requests to complete.

I wanted clients to have a good, fairly-unified experience, which guided
a few of my decisions. I overrode the default `write_error` method in Tornado
so that unimplemented methods/routes would return standardized JSON instead
of HTML errors. I also wanted the API to be easily accessible by an
automated system, so I standardized codes corresponding to various error
types. I implemented a versioning system for future expandability, and
I separated the Bitly API calls into their own library so that they could
be updated/modified separately from the web server as the Bitly API changes.

I was planning to build an additional "lite" version in Go, but decided to
put the extra time/effort into this project instead.

I developed the project in a Linux VM (where I do most of my personal dev
work), although I natively run MacOS. I used a Python virtual environment
to separate dependencies for this project. The only external dependencies
that I use are `tornado` and `urllib`, so the setup process should be
fairly straightforward. I chose port 8080 somewhat arbitrarily, but mostly
used it over port 80 so that special permissions would not be required to
run this API. That is easily changed by modifying a clearly marked variable
at the top of `server.py`. I asked Maria if the port should be easily
configurable when starting the server and did not get a response, so I left
it as a well-documented variable in the code.

I was originally planning to generate a `requirements.txt`, but with only two
dependencies that didn't seem necessary (but would be a good future extension).
I am happy to discuss any design decisions that I did not cover.

# Installation
1. Ensure Python 3.6.x+ is installed and in your path
1. Ensure `pip` is installed for Python 3
1. Put this project in your directory of choice
1. `cd` to the directory where this project is located
1. [optional] `pip install -U virtualenv` (install python virtual environment)
1. [optional] `virtualenv` (create the virtual environment)
1. [optional] `. venv/bin/activate` (activate the virtual environment)
1. `pip3 install tornado` (install tornado)
1. `pip3 install urllib` (install urllib)

# Running the API
After all dependencies are configured (inlcuding Python 3.6.x+), cd to the
`/src/` directory of this project and run `python3 server.py`.

Note that if you used a `venv` to install dependencies locally, that must be
active every time you run the server (unless you had the dependencies already
installed globally).

# Using the API
## Overview
There is a single main endpoint that will return the averaged country click
metrics per bitlink, discussed below. All errors are nicely-formatted and will
return a JSON body, as discussed below.

## Interacting with the API
The base url for this API is `http://[ip]:[port]`, where `ip` is the ip address
of the machine this is running on, and `port` is the port the API is set to
listen on. If you are running this locally with the default port, it becomes
`http://localhost:8080`.

There are two implemented endpoints:</br?>
`/`                      - [Base]    Get basic data about the API</br>
`/api/[version]/metrics` - [Metrics] Get the averaged country click metrics</br>

If you are using this version of the API, `version` is `v1`.

### Metrics Endpoint
You must do an HTTP `GET` to `/api/[version]/metrics` that includes your
`access_token` in the header as `access_token`. Postman is my preferred
API testing tool, but if you prefer cURL the following example will
successfully return the data, assuming you are running the API locally
with the given defaults:
```
curl -X GET \
  http://localhost:8080/api/v1/metrics \
  -H 'access_token: [your account access_token]'
```
`your account access_token` is the `access_token` associated with your Bitly
account.

The endpoint will return JSON as follows:
```
{
    "metrics": {
        "[bitlinkx]": {
            "[countryy]": float, [country metric xy],
            ...
        },
        ...
    },
    "uri": string, [uri that got here, e.g. "/api/v1/metrics"]
}
```
where `bitlinkx` is the bitlink in question, `countryy` is the country the metrics
are from, and `country metric xy` is the average number of clicks for `bitlinkx`
from `country` over the past 30 days.

### Base Endpoint
You must do an HTTP `GET` to `/`, and no parameters are required. A cURL example
of this is as follows:
`curl -X GET http://localhost:8080/`

The endpoint will return JSON as follows:
```
{
    "apiversion": string, [API version running],
    "apidocumentation": "In production I would give a doc link",
    "uri": "/"
}
```
Again, if this were in production I would include a real link to API documentation
in the `apidocumentation` field.

## API Errors
The API will return an HTTP `405` for unimplemented routes/methods, and anything
else that does not hit my other custom error handling. Those errors will return
a JSON body of the form:
```
{
    "error": {
        "code": int, [non-200 HTTP Status Code],
        "message": string, [standard message for that HTTP Status Code]
    }
}
```

Custom errors in the API will be returned in the form:
```
{
    "errortype": int, [error enum],
    "errormessage": string, [generally human-readable message describing the issue],
    "uri": string, [the API uri that was hit when this occured, e.g. "/api/v1/metrics"]
}
```
The `errortype`s are defined as follows:
`generic_internal_err = 1` - some otherwise-unclassified internal error occured
`bitly_api_data_err = 2`   - data returned from Bitly was formatted incorrectly
`bitly_api_http_err = 3`   - a non-200 HTTP status code was sent from the Bitly API
`bad_token_err = 4`        - the client provided an invalid access_token with their request

If the `errortype` is `3`, the `message` field will describe which HTTP status code was received.

# Testing
I have tested this API across the errors that I handle in the code, and have
tested simultaneous requests to verify that the async scheme works as
intended.