// A small JSONL boundary keeps the Hermes plugin Python-native while using
// Paseo's supported SDK for owned/reconnecting daemon event subscriptions.
import { createInterface } from 'node:readline';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { createPaseoClient } from '@getpaseo/client';

const output = frame => process.stdout.write(JSON.stringify(frame) + '\n');
const input = createInterface({ input: process.stdin });
const config = JSON.parse(await new Promise(resolve => input.once('line', resolve)));
input.close();
let authHeader;
if (config.home) {
  try {
    const credential = (await readFile(join(config.home, 'local-credential'), 'utf8')).trim();
    authHeader = `Bearer ${credential}`;
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
}
const client = createPaseoClient({
  url: config.url, authHeader,
  password: config.password || undefined,
  clientId: `hermes-executive-${process.pid}`,
  connectTimeoutMs: 15000,
  reconnect: { enabled: true, baseDelayMs: 1000, maxDelayMs: 15000 }
});
const heartbeat = setInterval(() => output({type: 'heartbeat'}), 10000);
const snapshot = agent => { if (agent?.id) output({type: 'snapshot', agent}); };
const listSubscriptions = [];
let eventSubscription;
try {
  await client.connect();
  client.agents.subscribe(update => snapshot(update.agent));
  let cursor;
  do {
    const listed = await client.agents.list({ filter: {includeArchived: false}, page: {limit: 200, ...(cursor ? {cursor} : {})}, subscribe: {} });
    for (const entry of listed.entries) snapshot(entry.agent ?? entry);
    listSubscriptions.push(listed.subscription);
    listed.subscription.subscribe({
      snapshot: page => { for (const entry of page.entries) snapshot(entry.agent ?? entry); },
      update: message => { if (message.type === 'agent_update') snapshot(message.payload.agent); },
      error: error => { output({type:'error', message:String(error)}); process.exitCode = 1; void close(); }
    });
    cursor = listed.pageInfo.nextCursor;
  } while (cursor);
  eventSubscription = client.observeEvents(['agent_permission_request', 'agent_permission_resolved', 'agent_attention_required']);
  eventSubscription.subscribe({
    snapshot() {},
    update: async message => {
      const id = message.payload?.agentId;
      if (id) {
        try { const handle = client.agents.ref(id); await handle.refresh(); snapshot(handle.current()); }
        catch (error) { output({type:'error', message:String(error)}); }
      }
    },
    error: error => output({type:'error', message:String(error)})
  });
  await eventSubscription.ready;
  output({type:'ready'});
} catch (error) {
  output({type:'error', message:String(error)});
  await close();
  process.exitCode = 1;
}
async function close() {
  clearInterval(heartbeat);
  await Promise.allSettled([...listSubscriptions.map(s => s.release()), eventSubscription?.release()]);
  await client.close();
}
process.on('SIGTERM', () => { void close().finally(() => process.exit()); });
process.on('SIGINT', () => { void close().finally(() => process.exit()); });
