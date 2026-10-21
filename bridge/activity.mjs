// Read-only timeline projection. Never forward reasoning, raw tool inputs, or credentials.
export async function readActivity(client, agentId, {limit=20, turnId=null, updatedAt=null}={}) {
  limit=Math.max(1,Math.min(limit,50));
  const page = await client.agents.ref(agentId).timeline.refetch({direction:'tail',limit,projection:'canonical'});
  if(page.error)throw new Error(page.error);
  const observed_at=Date.now()/1000;
  if(updatedAt && page.agent?.updatedAt && page.agent.updatedAt!==updatedAt){
    return {source:'paseo_sdk_timeline',scope:'newer_snapshot',observed_at,error:'Worker changed while activity was being read'};
  }
  let entries=(page.entries||[]).slice(-limit);
  if(turnId)entries=entries.filter(entry=>entry.turnId===turnId);
  let truncated=Boolean(page.hasOlder),budget=12000;
  const projected=[];
  for(const entry of entries.slice().reverse()){
    const item=entry.item||{};
    if(!['assistant_message','error','tool_call'].includes(item.type))continue;
    const original=item.type==='assistant_message'?item.text:item.type==='error'?item.message:item.error?String(item.error):null;
    const text=original?String(original).slice(0,Math.min(6000,budget)):null;
    if(original && text.length<String(original).length)truncated=true;
    budget-=text?.length||0;
    projected.push({type:item.type,...(text?{text}:{}),...(item.type==='tool_call'?{name:String(item.name||'').slice(0,200),status:item.status}:{}),
      timestamp:entry.timestamp,turn_id:entry.turnId||null,seq:entry.seqEnd});
    if(budget<=0){truncated=true;break;}
  }
  return {source:'paseo_sdk_timeline',format:'timeline',scope:turnId?'turn':'recent_activity',observed_at,
    entries:projected.reverse(),truncated,has_older:Boolean(page.hasOlder),cursor:page.endCursor||null};
}

export function snapshotEmitter(client, output, {timeoutMs=2000}={}) {
  const previous=new Map(),queues=new Map();
  return agent=>{
    if(!agent?.id)return Promise.resolve();
    agent=structuredClone(agent);
    const observedAt=Date.now()/1000;
    const work=(queues.get(agent.id)||Promise.resolve()).catch(()=>{}).then(async()=>{
      const old=previous.get(agent.id);
      previous.set(agent.id,agent);
      let activity;
      const ended=old && ['running','starting','initializing'].includes(old.status) && ['idle','error','failed'].includes(agent.status);
      if(ended){
        let timer;
        try{
          activity=await Promise.race([readActivity(client,agent.id,{turnId:old.activeTurn?.turnId,updatedAt:agent.updatedAt}),
            new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('Activity lookup timed out')),timeoutMs);})]);
        }catch(error){activity={source:'paseo_sdk_timeline',scope:'unknown',error:String(error),observed_at:Date.now()/1000};}
        finally{clearTimeout(timer);}
      }
      output({type:'snapshot',agent:{...agent,_executive_observed_at:observedAt,...(activity?{_executive_activity:activity}:{})}});
    });
    queues.set(agent.id,work);
    void work.finally(()=>{if(queues.get(agent.id)===work)queues.delete(agent.id);}).catch(()=>{});
    return work;
  };
}
