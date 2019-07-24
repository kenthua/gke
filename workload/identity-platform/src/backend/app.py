# Copyright 2019 Google LLC
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

from flask import Flask, jsonify, request
from flask_cors import CORS
import google.auth.transport.requests
import google.oauth2.id_token
import logging


HTTP_REQUEST = google.auth.transport.requests.Request()

app = Flask(__name__)
CORS(app)

@app.after_request
def set_response_headers(response):
    response.cache_control.max_age = 0
    response.cache_control.no_cache = True
    response.cache_control.no_store = True
    response.cache_control.must_revalidate = True
    response.cache_control.proxy_revalidate = True
    return response


@app.route('/api/secure.json')
def secret_message():
    if 'Authorization' in request.headers:        
        id_token = request.headers['Authorization'].split(' ').pop()
        logging.warning(id_token)
        claims = google.oauth2.id_token.verify_firebase_token(
            id_token, HTTP_REQUEST)

        # add the project id as the auth domain, for an additional check

        if not claims:
            return 'Unauthorized', 401
        logging.warning(claims)

        return jsonify({"message": "Hello World Standalone"})
    else:
        return 'Unauthorized', 401


@app.route('/api/healthz')
def healthz():
    return "ok"
