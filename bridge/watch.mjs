// A small JSONL boundary keeps the Hermes plugin Python-native while using
// Paseo's supported SDK for owned/reconnecting daemon event subscriptions.
import { createInterface } from 'node:readline';
import {configuredClient} from './connection.mjs';
import {snapshotEmitter} from './activity.mjs';

const output = frame => process.stdout.write(JSON.stringify(frame) + '\n');
const input = createInterface({ input: process.stdin });
const config = JSON.parse(await new Promise(resolve => input.once('line', resolve)));
input.close();
const client = await configuredClient(config);
const snapshot = snapshotEmitter(client,output);

const heartbeat = setInterval(() => output({type: 'heartbeat'}), 10000);
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
