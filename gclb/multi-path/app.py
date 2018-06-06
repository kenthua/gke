# Copyright 2015 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# [START app]
import logging
import socket

from flask import Flask

app = Flask(__name__)
strHostname = socket.gethostname()

@app.route('/')
def root():
    """Return a friendly HTTP greeting."""

    logging.info('INFO: service1')

    return 'Hello World - root - %s' % (strHostname)

@app.route('/service1')
def hello1():
    """Return a friendly HTTP greeting."""

    logging.info('INFO: service1')

    return 'Hello World - service1! - %s' % (strHostname)

@app.route('/service2')
def hello2():
    """Return a friendly HTTP greeting."""

    logging.info('INFO: service2')

    return 'Hello World - service2! - %s' % (strHostname)

@app.errorhandler(500)
def server_error(e):
    logging.exception('An error occurred during a request.')
    return """
    An internal error occurred: <pre>{}</pre>
    See logs for full stacktrace.
    """.format(e), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
# [END app]