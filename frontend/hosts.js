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
