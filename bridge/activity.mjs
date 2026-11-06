// Read-only timeline projection. Preserve bounded tool results, excluding reasoning and raw inputs.
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
  // SDK canonical tool results live in detail, not on the tool_call itself.
  const resultFields = {
    shell:['output','exitCode'], read:['filePath','content'],
    edit:['filePath','unifiedDiff','oldString','newString'], write:['filePath','content'],
    search:['content','filePaths','webResults','numFiles','numMatches','truncated'],
    fetch:['result','code','codeText','bytes'], worktree_setup:['worktreePath','branchName','log'],
    sub_agent:['log'], plain_text:['text'], plan:['text'], unknown:['output']
  };
  const boundedResult=(value,depth=0)=>{
    if(budget<=0 || depth>5){truncated=true;return '[truncated]';}
    if(typeof value==='string'){
      const text=value.slice(0,Math.min(6000,budget));
      budget-=text.length;if(text.length<value.length)truncated=true;
      return text;
    }
    if(value && typeof value==='object'){
      const pairs=Array.isArray(value)?value.map((v,i)=>[i,v]):Object.entries(value);
      const out=Array.isArray(value)?[]:{};
      if(pairs.length>20)truncated=true;
      for(const [key,v] of pairs.slice(0,20)){
        if(budget<=0){truncated=true;break;}
        budget-=String(key).length+4;
        out[key]=boundedResult(v,depth+1);
      }
      return out;
    }
    budget-=16;
    return value;
  };
  for(const entry of entries.slice().reverse()){
    const item=entry.item||{};
    if(!['assistant_message','error','tool_call'].includes(item.type))continue;
    const original=item.type==='assistant_message'?item.text:item.type==='error'?item.message:item.error?String(item.error):null;
    const text=original?String(original).slice(0,Math.min(6000,budget)):null;
    if(original && text.length<String(original).length)truncated=true;
    budget-=text?.length||0;
    let detail;
    if(item.type==='tool_call' && item.detail){
      detail={type:item.detail.type};
      for(const field of resultFields[item.detail.type]||[]){
        if(item.detail[field]!==undefined)detail[field]=boundedResult(item.detail[field]);
      }
    }
    projected.push({type:item.type,...(text?{text}:{}),...(item.type==='tool_call'?{name:String(item.name||'').slice(0,200),status:item.status,call_id:item.callId,...(detail?{detail}:{})}:{}),
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
