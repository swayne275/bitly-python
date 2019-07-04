# bitly-python
Python solution to Bitly's backend coding challenge

# Summary
This is a solution to the bitly_backend_test, written in Python 3 using
Tornado as the primary library to both serve the API and interact with
the relevant Bitly API endpoints. The goal is to provide a reasonably
performant API that exposes the average number of daily clicks Bitlinks
in the user's default group received from each country over the last 30 days.

# Design Decisions
I chose Python and Tornado because I have already written a reasonably
performant API using these technologies for my previous work/projects,
and I was limited on how much time I could dedicate to this project. Those
APIs, however, did not interact with another REST API, and were mostly
synchronous. I also knew that Tornado could host static assets in case
I ever wanted to build a simple GUI to interact with the Bitly API.

I originally used the `response` Python library to synchronously interact
with the Bitly API, but later transitioned to use Tornado's AsyncHTTPClient.
Since this project is inherently IO bound (most of the time is spent
waiting on Bitly's API) it made sense to build this as an async API so
that multiple clients could use it simultaneously without serially
waiting on Bitly API requests to complete.

I wanted clients to have a good, fairly-unified experience, which guided
a few of my decisions. I overrode the default `write_error` method so that
unimplemented methods/routes would return standardized JSON instead of
HTML errors. I also wanted the API to be easily accessible by an
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
at the top of `server.py`. I am happy to discuss any design decisions that
I did not cover in this summary

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

# Using the API
There is a single main endpoint, located at `{ip}:{port}/api/{version}/metrics`
that will return data in the JSON format, discussed below. If you are running
this locally without modification, it is accessed with an HTTP `GET` to
`localhost:8080/api/v1/metrics`. There is also a handler for `/` that provides
`{version}` and a dummy link to API documentation via a `GET`. To use this
API you must know your Bitly `access_token` and provide it in the header of
your request.

To properly authenticate with the Bitly API, all of your `/api/{version}/metrics`
requests must have a header field, `access_token`, where you provide the
`access_token` associated with your Bitly account. The response will be of the
form:
```
{
    "[bitlink1]": {
        "[country1]": float, [avg # clicks from [country1] over past 30 days],
        ...
    },
    ...
}
```


# Testing
I have tested this API across the errors that I handle in the code, and have
tested simultaneous requests to verify that the async scheme works as
intended.