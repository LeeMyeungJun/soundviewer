const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync, existsSync } = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '..');

function worker() {
  const listeners = {};
  const storage = new Map();
  const messages = [];
  const network = [];
  let fail = '';
  let offline = false;
  const scope = 'https://example.test/soundviewer/';
  const fetch = async (input) => {
    const url = String(input);
    network.push(url);
    if (offline || url.endsWith(fail || '__never__')) throw new Error('offline');
    return new Response(Uint8Array.from([0,1,2,3,4,5,6,7,8,9]), { headers: { 'Content-Type': url.endsWith('.mp3') ? 'audio/mpeg' : 'text/plain' } });
  };
  const caches = {
    async open(name) {
      if (!storage.has(name)) storage.set(name, new Map());
      const entries = storage.get(name);
      return {
        async match(url) { return entries.get(String(url))?.clone(); },
        async put(url, response) { entries.set(String(url), response.clone()); },
        async addAll(urls) { for (const url of urls) entries.set(url, await fetch(url)); },
      };
    },
    async keys() { return [...storage.keys()]; },
    async delete(name) { return storage.delete(name); },
  };
  const self = {
    registration: { scope },
    SOUND_CATALOG: [{ image: 'assets/images/dog.png', audio: 'assets/audio/dog.mp3' }],
    addEventListener(type, fn) { listeners[type] = fn; },
    skipWaiting: async () => {},
    clients: { claim: async () => {}, matchAll: async () => [{ postMessage: (value) => messages.push(value) }] },
  };
  vm.runInNewContext(readFileSync(path.join(root, 'sw.js'), 'utf8'), { self, caches, fetch, URL, Headers, Response, importScripts() {} });
  async function dispatch(type, props = {}) {
    let result;
    listeners[type]({ ...props, waitUntil: (promise) => { result = promise; }, respondWith: (promise) => { result = promise; } });
    return result;
  }
  return { scope, storage, messages, network, dispatch, setFailure: (value) => { fail = value; }, setOffline: () => { offline = true; } };
}

test('first visit stores all files; repeated requests work offline without network', async () => {
  const w = worker();
  await w.dispatch('install');
  await w.dispatch('message', { data: { type: 'CACHE_ALL' } });
  assert.equal(w.messages.at(-1).complete, true);
  assert.equal(w.messages.at(-1).done, 10);
  assert.ok(w.network.every((url) => url.startsWith(w.scope)));
  const before = w.network.length;
  w.setOffline();
  for (const relative of ['', 'index.html', 'credits.html', 'credits.js', 'assets/images/dog.png', 'assets/audio/dog.mp3']) {
    const result = await w.dispatch('fetch', { request: new Request(w.scope + relative) });
    assert.equal(result.status, 200);
  }
  await w.dispatch('message', { data: { type: 'CACHE_ALL' } });
  assert.equal(w.network.length, before);
});

test('interrupted precaching reports failure and retries only missing files', async () => {
  const w = worker();
  await w.dispatch('install');
  w.setFailure('dog.mp3');
  await w.dispatch('message', { data: { type: 'CACHE_ALL' } });
  assert.equal(w.messages.at(-1).complete, false);
  assert.equal(w.messages.at(-1).error, true);
  const before = w.network.length;
  w.setFailure('');
  await w.dispatch('message', { data: { type: 'CACHE_ALL' } });
  assert.equal(w.messages.at(-1).complete, true);
  assert.equal(w.network.length - before, 1);
});

test('cached Safari byte ranges return correct bytes, lengths, and errors', async () => {
  const w = worker();
  await w.dispatch('message', { data: { type: 'CACHE_ALL' } });
  w.setOffline();
  for (const [range, status, bytes, contentRange] of [
    ['bytes=0-1', 206, [0,1], 'bytes 0-1/10'],
    ['bytes=7-', 206, [7,8,9], 'bytes 7-9/10'],
    ['bytes=-3', 206, [7,8,9], 'bytes 7-9/10'],
    ['bytes=8-9999', 206, [8,9], 'bytes 8-9/10'],
    ['bytes=10-', 416, [], 'bytes */10'],
    ['bytes=5-2', 416, [], 'bytes */10'],
    ['bytes=-', 416, [], 'bytes */10'],
  ]) {
    const response = await w.dispatch('fetch', { request: new Request(w.scope + 'assets/audio/dog.mp3', { headers: { Range: range } }) });
    assert.equal(response.status, status, range);
    assert.equal(response.headers.get('Content-Range'), contentRange, range);
    assert.deepEqual([...new Uint8Array(await response.arrayBuffer())], bytes, range);
    if (status === 206) assert.equal(Number(response.headers.get('Content-Length')), bytes.length);
  }
});

test('old scoped caches survive incomplete downloads; unrelated caches are retained', async () => {
  const w = worker();
  const old = `soundviewer:${w.scope}:v0`;
  w.storage.set(old, new Map());
  w.storage.set('another-app', new Map());
  w.setFailure('dog.mp3');
  await w.dispatch('message', { data: { type: 'CACHE_ALL' } });
  assert.ok(w.storage.has(old));
  w.setFailure('');
  await w.dispatch('message', { data: { type: 'CACHE_ALL' } });
  assert.equal(w.storage.has(old), false);
  assert.ok(w.storage.has('another-app'));
});

test('every real catalog item includes existing media and complete sound attribution', () => {
  const context = {};
  vm.runInNewContext(readFileSync(path.join(root, 'catalog.js'), 'utf8'), context);
  assert.equal(context.SOUND_CATALOG.length, 20);
  assert.equal(new Set(context.SOUND_CATALOG.map((item) => item.id)).size, 20);
  for (const item of context.SOUND_CATALOG) {
    assert.ok(existsSync(path.join(root, item.image)), item.image);
    assert.ok(existsSync(path.join(root, item.audio)), item.audio);
    assert.ok(item.duration > 0 && item.duration < 15.1);
    assert.ok(item.credit.author && item.credit.license && item.credit.source.startsWith('https://'));
    assert.match(item.credit.originalSha256, /^[a-f0-9]{64}$/);
  }
});
