'use strict';

const http = require('http');
const assert = require('assert');

// 1. Mock upstream services
let failDiscovery = false;
const mockServer = http.createServer((req, res) => {
  if (req.url === '/discovery') {
    if (failDiscovery) {
      res.writeHead(500);
      res.end('Upstream Error');
      return;
    }
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      items: [
        { name: 'compute' },
        { name: 'storage' }
      ]
    }));
  } else if (req.url === '/posts') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify([
      { id: 1, title: 'Sample Post' }
    ]));
  } else {
    res.writeHead(404);
    res.end();
  }
});

mockServer.listen(0, async () => {
  const mockPort = mockServer.address().port;
  process.env.ENABLE_TRACE = 'false';
  process.env.DISCOVERY_URL = `http://127.0.0.1:${mockPort}/discovery`;
  process.env.ALT_URL = `http://127.0.0.1:${mockPort}/posts`;

  const app = require('./app');
  const server = app.listen(0, async () => {
    const appPort = server.address().port;

    try {
      // Test 1: Successful request
      const res1 = await fetch(`http://127.0.0.1:${appPort}/`);
      assert.strictEqual(res1.status, 200, 'Expected status 200');
      const body1 = await res1.text();
      assert.ok(body1.startsWith('v2'), 'Body should start with v2');
      assert.ok(body1.includes('compute\nstorage'), 'Body should include discovered API names');
      assert.ok(body1.includes('Sample Post'), 'Body should include alt response');
      console.log('✓ Test 1 Passed: GET / returned expected content');

      // Test 2: Error handling when upstream fails
      failDiscovery = true;
      const res2 = await fetch(`http://127.0.0.1:${appPort}/`);
      assert.strictEqual(res2.status, 500, 'Expected status 500 on upstream error');
      console.log('✓ Test 2 Passed: GET / handles upstream error gracefully');

      console.log('\nAll nodejs-trace tests passed successfully!');
    } catch (err) {
      console.error('Test failed:', err);
      process.exitCode = 1;
    } finally {
      server.close();
      mockServer.close();
    }
  });
});
