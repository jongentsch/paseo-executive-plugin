import React from 'react';
import {host,useQuery,useMutation,useQueryClient,queryClient} from '@hermes/plugin-sdk';
const h = React.createElement;
// Shared by the native Settings page, worker pane, and web dashboard.
const hostCard = {border:'1px solid var(--ui-stroke-secondary, #7774)', borderRadius:10, padding:16, marginBottom:16};
const hostControl = {padding:'7px 10px', border:'1px solid var(--ui-stroke-secondary, #7775)', borderRadius:6, background:'transparent', color:'inherit', font:'inherit', width:'100%', boxSizing:'border-box'};
const emptyHost = () => ({id:'', label:'', type:'local', home:'~/.paseo', target:'', stream_url:'', password_env:'', enabled:true});
function HostSettings({data, error, act, busy, embedded=false}) {
  const [draft, setDraft] = React.useState(null);
  const [editing, setEditing] = React.useState(false);
  const [feedback, setFeedback] = React.useState('');
  const hosts = data?.hosts || [];
  const update = (key, value) => setDraft(previous => ({...previous, [key]:value}));
  const text = (label, key, placeholder, disabled=false) => h('label', {style:{display:'grid', gap:5, marginBottom:12}}, label,
    h('input', {style:hostControl, value:draft[key], placeholder, disabled:busy||disabled, onChange:event=>update(key,event.target.value)}));
  const button = (label, onClick, disabled=false) => h('button', {
    type:'button', disabled:busy||disabled, onClick, style:{...hostControl, width:'auto', cursor:'pointer'}
  }, label);
  const request = async args => {
    setFeedback('');
    try { return await act({name:'paseo_hosts',args}); }
    catch (failure) { setFeedback(String(failure.message||failure)); return null; }
  };
  const edit = host => {
    setEditing(true);
    setFeedback('');
    setDraft({...emptyHost(), ...host, type:host.home?'local':host.target?.startsWith('ssh://')?'ssh':'remote'});
  };
  const submit = async event => {
    event.preventDefault();
    let target = draft.target.trim();
    if (draft.type==='ssh' && !target.startsWith('ssh://')) target='ssh://'+target;
    const args = {action:editing?'update':'add', host_id:draft.id.trim(), label:draft.label.trim(), enabled:draft.enabled,
      ...(draft.type==='local'?{home:draft.home.trim()}:{target}),
      ...(draft.stream_url.trim()?{stream_url:draft.stream_url.trim()}:{}),
      ...(draft.password_env.trim()?{password_env:draft.password_env.trim()}: {})};
    if (await request(args)) {setDraft(null);setFeedback(editing?'Host updated.':'Host added.');}
  };
  return h('section', {style:embedded?hostCard:{padding:20, maxWidth:900}},
    h('h2', {style:{fontSize:embedded?18:24, marginTop:0}}, 'Paseo hosts'),
    h('p', {style:{opacity:.75}}, 'Add the machines where Hermes can run coding workers. Each host has its own connection and workers.'),
    (error||data?.config_error) && h('div',{role:'alert',style:hostCard},String(error?.message||error||data.config_error)),
    feedback && h('p', {role:'status'}, feedback),
    !data && !error && h('p',null,'Loading hosts…'),
    data && !hosts.length && h('p',null,'No hosts configured. Add a local daemon, remote daemon, or SSH host.'),
    ...hosts.map(host => h('article',{key:host.id,style:hostCard},
      h('strong', null, host.label||host.id),
      h('p',{style:{opacity:.7,overflowWrap:'anywhere'}},`${host.id} · ${host.home?'Local':host.target?.startsWith('ssh://')?'SSH':'Remote'} · ${host.home||host.target}`),
      h('p',{style:{opacity:.7}},!host.enabled?'Monitoring paused':host.health?.error?`Connection failed: ${host.health.error}`:host.health?.connected?'Connected':'Connection not checked'),
      h('div',{style:{display:'flex',gap:8,flexWrap:'wrap'}},
        button('Edit',()=>edit(host)),
        button('Check connection',async()=>{const result=await request({action:'probe',host_id:host.id});if(result)setFeedback(`${host.label||host.id}: connection successful.`);}),
        button(host.enabled?'Pause monitoring':'Resume monitoring',()=>request({...host,action:'update',host_id:host.id,enabled:!host.enabled})),
        button('Remove',async()=>{if(await request({action:'remove',host_id:host.id})){if(draft?.id===host.id)setDraft(null);setFeedback('Host removed. Its workers keep running.');}})))),
    !draft && button('Add host',()=>{setDraft(emptyHost());setEditing(false);setFeedback('');}),
    draft && h('form',{onSubmit:submit,style:hostCard},
      h('h3',null,editing?'Edit host':'Add host'),
      text('Host ID','id','linux-worker',editing),
      text('Display name','label','Linux worker'),
      h('label',{style:{display:'grid',gap:5,marginBottom:12}},'Connection type',
        h('select',{style:hostControl,value:draft.type,disabled:busy,onChange:event=>{update('type',event.target.value);update('stream_url','');update('password_env','');}},
          h('option',{value:'local'},'Local daemon'),h('option',{value:'remote'},'Remote daemon'),h('option',{value:'ssh'},'SSH host'))),
      draft.type==='local'?text('Paseo home directory','home','~/.paseo'):draft.type==='ssh'?text('SSH destination','target','user@devbox or ssh://user@devbox'):text('Daemon address or pairing link','target','devbox:6767'),
      h('p',{style:{opacity:.7}},draft.type==='local'?'Choose the Paseo daemon home on this machine.':draft.type==='ssh'?'Uses your existing SSH configuration and keys through Paseo.':'Use the address or pairing link for this Paseo daemon.'),
      h('details',null,h('summary',null,'Advanced connection options'),
        text('Direct live-event URL (optional)','stream_url','wss://devbox.example/ws'),
        text('Password secret name (optional)','password_env','PASEO_DEVBOX_PASSWORD'),
        h('p',{style:{opacity:.7}},'Without a direct event URL, remote and SSH hosts use periodic status checks. Enter a secret name here, never a password.')),
      h('label',{style:{display:'flex',gap:8,margin:'12px 0'}},
        h('input',{type:'checkbox',checked:draft.enabled,onChange:event=>update('enabled',event.target.checked)}),'Monitor this host'),
      h('div',{style:{display:'flex',gap:8}},
        h('button',{type:'submit',style:{...hostControl,width:'auto'},disabled:busy||!draft.id.trim()||!(draft.type==='local'?draft.home.trim():draft.target.trim())},editing?'Save changes':'Add host'),
        button('Cancel',()=>setDraft(null)))));
}

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
