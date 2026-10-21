import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readActivity,snapshotEmitter} from '../bridge/activity.mjs';

function client(page){return {agents:{ref(){return {timeline:{refetch:async options=>{assert.equal(options.direction,'tail');assert.equal(options.projection,'canonical');return typeof page==='function'?page():page;}}};}}};}

test('timeline projection preserves worker replies and excludes private tool inputs and reasoning',async()=>{
  const api=client({agent:{updatedAt:'v1'},entries:[
    {item:{type:'reasoning',text:'private reasoning'},turnId:'t1'},
    {item:{type:'tool_call',name:'shell',status:'completed',input:{token:'secret-input'},output:'full output'},turnId:'t1'},
    {item:{type:'assistant_message',text:'Old reply'},turnId:'t0'},
    {item:{type:'assistant_message',text:'The result'},turnId:'t1'}]});
  const activity=await readActivity(api,'worker',{turnId:'t1',updatedAt:'v1'});
  assert.equal(activity.scope,'turn');
  assert.equal(activity.entries.at(-1).text,'The result');
  assert.ok(!JSON.stringify(activity).includes('secret-input'));
  assert.ok(!JSON.stringify(activity).includes('private reasoning'));
  assert.ok(!JSON.stringify(activity).includes('Old reply'));
});

test('different snapshot version refuses a stale report',async()=>{
  const activity=await readActivity(client({agent:{updatedAt:'new'},entries:[]}), 'worker',{updatedAt:'old'});
  assert.equal(activity.scope,'newer_snapshot');assert.ok(activity.error);
});

test('activity text is bounded',async()=>{
  const activity=await readActivity(client({entries:Array.from({length:20},()=>({item:{type:'assistant_message',text:'x'.repeat(10000)}}))}),'worker');
  assert.ok(activity.truncated);assert.ok(activity.entries.reduce((n,e)=>n+(e.text?.length||0),0)<=12000);
});

test('async enrichment keeps rapid turns in observed order',async()=>{
  const output=[];
  let count=0;
  const api=client(async()=>{await new Promise(resolve=>setTimeout(resolve,5));count++;return {agent:{updatedAt:'v'+count},entries:[{item:{type:'assistant_message',text:'Reply '+count},turnId:'t'+count}]};});
  const emit=snapshotEmitter(api,frame=>output.push(frame));
  await Promise.all([
    emit({id:'a',status:'running',activeTurn:{turnId:'t1'}}),
    emit({id:'a',status:'idle',updatedAt:'v1'}),
    emit({id:'a',status:'running',activeTurn:{turnId:'t2'}}),
    emit({id:'a',status:'idle',updatedAt:'v2'})]);
  assert.deepEqual(output.map(frame=>frame.agent.status),['running','idle','running','idle']);
  assert.equal(output[1].agent._executive_activity.entries[0].text,'Reply 1');
  assert.equal(output[3].agent._executive_activity.entries[0].text,'Reply 2');
});

test('lookup failure still emits the terminal snapshot',async()=>{
  const output=[];
  const emit=snapshotEmitter(client(()=>{throw new Error('unavailable');}),frame=>output.push(frame));
  await emit({id:'a',status:'running'});await emit({id:'a',status:'idle'});
  assert.equal(output.length,2);assert.equal(output[1].agent.status,'idle');assert.match(output[1].agent._executive_activity.error,/unavailable/);
});

test('queued snapshots capture values before callers can mutate them',async()=>{
  const output=[];
  const emit=snapshotEmitter(client({entries:[]}),frame=>output.push(frame));
  const agent={id:'a',status:'running',activeTurn:{turnId:'t1'}};
  const queued=emit(agent);
  agent.status='idle';agent.activeTurn.turnId='different';
  await queued;
  assert.equal(output[0].agent.status,'running');
  assert.equal(output[0].agent.activeTurn.turnId,'t1');
});
