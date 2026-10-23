/**
 * Copyright 2017, Google, Inc.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

'use strict';

// [START trace_app]
if (process.env.ENABLE_TRACE !== 'false') {
  try {
    require('@google-cloud/trace-agent').start();
  } catch (err) {
    console.warn('Trace agent failed to start:', err.message);
  }
}

const express = require('express');

let gotInstance;
async function getGot() {
  if (!gotInstance) {
    try {
      const rawGot = require('got');
      gotInstance = rawGot.default || rawGot;
    } catch {
      const rawGot = await import('got');
      gotInstance = rawGot.default || rawGot;
    }
  }
  return gotInstance;
}

const app = express();
const DISCOVERY_URL = process.env.DISCOVERY_URL || 'https://www.googleapis.com/discovery/v1/apis';
const ALT_URL = process.env.ALT_URL || 'https://jsonplaceholder.typicode.com/posts';

// This incoming HTTP request should be captured by Trace
app.get('/', async (req, res) => {
  try {
    const got = await getGot();
    // These outgoing HTTP requests should be captured by Trace
    const [discoveryResponse, altResponse] = await Promise.all([
      got(DISCOVERY_URL, { responseType: 'json' }),
      got(ALT_URL, { responseType: 'json' })
    ]);

    const names = (discoveryResponse.body && discoveryResponse.body.items)
      ? discoveryResponse.body.items.map((item) => item.name)
      : [];

    const altBody = typeof altResponse.body === 'string'
      ? altResponse.body
      : JSON.stringify(altResponse.body);

    res
      .status(200)
      .send('v2' + names.join('\n') + altBody)
      .end();
  } catch (err) {
    console.error(err);
    if (!res.headersSent) {
      res
        .status(500)
        .end();
    }
  }
});

// Start the server
const PORT = process.env.PORT || 8080;
if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`App listening on port ${PORT}`);
    console.log('Press Ctrl+C to quit.');
  });
}

module.exports = app;
// [END trace_app]
