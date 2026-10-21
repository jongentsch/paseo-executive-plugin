"""Build dependency-free React entrypoints for Hermes' two plugin SDKs."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
shared = 'const h = React.createElement;\n' + (root/'frontend/hosts.js').read_text() + r'''
function Panel({data, error, act, busy}) {
  const [host, setHost] = React.useState('local');
  const [prompt, setPrompt] = React.useState('');
  const [cwd, setCwd] = React.useState('');
  const [provider, setProvider] = React.useState('codex');
  const hosts = data?.hosts || [];
  const agents = data?.agents || [];
  const events = data?.events || [];
  const permissions = agents.flatMap(a => (a.pendingPermissions || []).map(p => ({...p, agent:a})));
  const card = {border:'1px solid var(--ui-stroke-secondary, #7774)', borderRadius:10, padding:16, marginBottom:16};
  const control = {padding:'7px 10px',border:'1px solid var(--ui-stroke-secondary, #7775)',borderRadius:6,background:'transparent',color:'inherit',font:'inherit',maxWidth:'100%'};
  const button = (label, click, disabled=false) => h('button',{type:'button',style:{...control,cursor:'pointer'},onClick:click,disabled:busy||disabled},label);
  const input = (label, value, set, placeholder) => h('label',{style:{display:'grid',gap:5,marginBottom:10}},label,h('input',{value,onChange:e=>set(e.target.value),placeholder,style:control}));
  const call = async (name, args, confirmed=false) => {try{return await act({name,args,user_confirmed:confirmed})}catch{return null}};
  return h('div',{style:{padding:20,maxWidth:1100,margin:'auto',overflow:'auto',height:'100%',fontSize:14}},
    h('header',{style:{display:'flex',justifyContent:'space-between',alignItems:'center',gap:12,marginBottom:20}},
      h('div',null,h('h2',{style:{fontSize:24,fontWeight:650,margin:0}},'Paseo Executive'),
        h('p',{style:{opacity:.65,margin:'6px 0'}},'Delegate work. Review decisions. Stay informed.')),
      button(data?.monitor_enabled?'Pause monitoring':'Start monitoring',()=>call('paseo_subscribe',{action:data?.monitor_enabled?'stop':'start'}))),
    error && h('div',{role:'alert',style:card},String(error.message||error)),
    !data && !error && h('p',null,'Connecting to the executive service…'),
    h(HostSettings,{data,error,act,busy,embedded:true}),
    h('section',{style:card},h('h3',null,'Delegate a task'),
      h('div',{style:{display:'flex',gap:12,flexWrap:'wrap'}},
        h('label',null,'Host ',h('select',{value:host,onChange:e=>setHost(e.target.value),style:control},...hosts.map(x=>h('option',{key:x.id,value:x.id},x.label||x.id)))),
        h('label',null,'Provider ',h('select',{value:provider,onChange:e=>setProvider(e.target.value),style:control},h('option',{value:'codex'},'Codex'),h('option',{value:'claude'},'Claude')))),
      input('Working directory on host',cwd,setCwd,'/path/to/project'),
      h('label',{style:{display:'grid',gap:6,marginBottom:10}},'Task',h('textarea',{value:prompt,onChange:e=>setPrompt(e.target.value),rows:3,style:control,placeholder:'Describe the outcome and acceptance criteria…'})),
      button('Spawn worker',async()=>{const result=await call('paseo_spawn',{host_id:host,prompt,cwd,provider});if(result)setPrompt('');},!prompt||!cwd||!hosts.some(x=>x.id===host))),
    h('section',{style:card},h('h3',null,`Needs your decision (${permissions.length})`),
      !permissions.length && h('p',{style:{opacity:.65}},'No pending permission requests.'),
      ...permissions.map(p=>h('article',{key:`${p.agent.host_id}:${p.agent.id}:${p.id}`,style:card},
        h('strong',null,`${p.agent.host_id} / ${p.agent.name||p.agent.id}`),
        h('pre',{style:{whiteSpace:'pre-wrap',wordBreak:'break-word',fontSize:12}},JSON.stringify(p,null,2)),
        h('div',{style:{display:'flex',gap:10}},...['allow','deny'].map(decision=>button(decision==='allow'?'Allow this request':'Deny this request',()=>call('paseo_decide_permission',{
          host_id:p.agent.host_id,agent_id:p.agent.id,request_id:p.id,decision},true))))))),
    h('section',{style:card},h('h3',null,`Workers (${agents.length})`),
      !agents.length && h('p',{style:{opacity:.65}},'Workers will appear after the first host sync.'),
      ...agents.map(a=>h('div',{key:a.host_id+':'+a.id,style:{padding:'9px 0',borderBottom:'1px solid var(--ui-stroke-secondary, #7773)'}},
        h('div',{style:{display:'flex',justifyContent:'space-between',gap:10}},h('strong',null,a.name||a.id),h('span',null,a.status)),
        h('div',{style:{opacity:.65,fontSize:12}},`${a.host_id} · ${a.provider||''} · ${a.id}`),
        a.lastError && h('pre',{style:{whiteSpace:'pre-wrap'}},JSON.stringify(a.lastError)),
        a.status==='running' && button('Interrupt',()=>call('paseo_agents',{action:'stop',host_id:a.host_id,agent_id:a.id}))))),
    h('section',{style:card},h('h3',null,'Recent activity'),
      ...events.slice().reverse().slice(0,30).map(e=>h('div',{key:e.id,style:{padding:'8px 0',fontSize:12}},
        h('strong',null,`${e.kind} · ${e.host}`),h('span',{style:{opacity:.65}},` · ${e.agent||''} · ${new Date(e.created*1000).toLocaleString()} · ${e.delivered?'sent to Hermes':'in outbox'}`),
        h('pre',{style:{whiteSpace:'pre-wrap',wordBreak:'break-word'}},JSON.stringify(e.data))))));
}
'''
web = '''(function(){'use strict';
const SDK=window.__HERMES_PLUGIN_SDK__;
const React=SDK.React;
'''+shared+'''
function Page(){
  const [data,setData]=React.useState(null),[error,setError]=React.useState(null),[busy,setBusy]=React.useState(false);
  const load=()=>SDK.fetchJSON('/api/plugins/paseo-executive/state').then(d=>{setData(d);setError(null)}).catch(setError);
  React.useEffect(()=>{let active=true;const refresh=()=>{if(active)void load()};refresh();const timer=setInterval(refresh,5000);return()=>{active=false;clearInterval(timer)}},[]);
  const act=async body=>{setBusy(true);try{const result=await SDK.fetchJSON('/api/plugins/paseo-executive/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});await load();return result}catch(e){setError(e);throw e}finally{setBusy(false)}};
  return h(Panel,{data,error,act,busy});
}
window.__HERMES_PLUGINS__.register('paseo-executive',Page);
})();
'''
desktop = '''import React from 'react';
import {host,useQuery,useMutation,useQueryClient,queryClient} from '@hermes/plugin-sdk';
'''+shared+'''
function DesktopPanel({ctx,settings=false}){
  const client=useQueryClient();
  const query=useQuery({queryKey:['paseo-executive','state'],queryFn:()=>ctx.rest('/state'),refetchInterval:5000});
  const mutation=useMutation({mutationFn:body=>ctx.rest('/action',{method:'POST',body}),onSuccess:()=>client.invalidateQueries({queryKey:['paseo-executive','state']})});
  const act=async body=>{try{return await mutation.mutateAsync(body)}catch(e){host.notifyError(e,'Paseo action failed');throw e}};
  return h(settings?HostSettings:Panel,{data:query.data,error:query.error||mutation.error,act,busy:mutation.isPending});
}
export default {
  id:'paseo-executive',name:'Paseo Executive',
  register(ctx){
    ctx.register({id:'executive',area:'panes',title:'Paseo Executive',data:{placement:'right',width:'480px'},render:()=>h(DesktopPanel,{ctx})});
    const settings={id:'hosts',title:'Paseo Executive',icon:'server',render:()=>h(DesktopPanel,{ctx,settings:true})};
    if(ctx.registerSettingsPage)ctx.registerSettingsPage(settings);
    else ctx.register({...settings,area:'settings.plugins',data:{icon:'server'}});
    const seen=new Set();
    ctx.onDispose(host.onEvent('plugin.paseo-executive.worker.event',({payload})=>{
      queryClient.invalidateQueries({queryKey:['paseo-executive','state']});
      if(seen.has(payload.id))return;seen.add(payload.id);
      const title=`Paseo ${payload.kind}`;
      const message=`${payload.host} / ${payload.agent}`;
      host.notify({kind:payload.kind==='failed'?'error':'info',title,message});
      ctx.os.notify({title,body:message});
    }));
  }
};
'''
(root/'dashboard/dist/index.js').write_text(web)
(root/'desktop/plugin.js').write_text(desktop)
print('Built dashboard and desktop bundles')
