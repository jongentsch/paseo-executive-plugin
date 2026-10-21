const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function harness(data={hosts:[]}) {
  const state=[]; let cursor=0;
  const calls=[];
  const h=(type,props,...children)=>({type,props:{...props,children:children.flat(Infinity).filter(c=>c!==null&&c!==undefined&&c!==false)}});
  const React={createElement:h,useState(initial){
    const slot=cursor++;
    if(!(slot in state))state[slot]=initial;
    return [state[slot],value=>state[slot]=typeof value==='function'?value(state[slot]):value];
  }};
  const context={React,h};
  vm.createContext(context);
  vm.runInContext(fs.readFileSync('frontend/hosts.js','utf8')+'\nthis.Component=HostSettings;',context);
  const render=()=>{cursor=0;return context.Component({data,act:async body=>{calls.push(JSON.parse(JSON.stringify(body)));return {ok:true};},busy:false});};
  const all=(node,predicate)=>{
    if(!node||typeof node!=='object')return [];
    return [...(predicate(node)?[node]:[]),...node.props.children.flatMap(child=>all(child,predicate))];
  };
  const text=node=>typeof node==='object'?node.props.children.map(text).join(''):String(node);
  const button=label=>all(render(),node=>node.type==='button'&&text(node)===label)[0];
  const field=label=>all(render(),node=>node.type==='label'&&node.props.children[0]===label)[0]?.props.children.find(child=>typeof child==='object');
  return {render,all,button,field,calls,change(label,value){field(label).props.onChange({target:{value}});},
    submit:()=>all(render(),node=>node.type==='form')[0].props.onSubmit({preventDefault(){}})};
}

test('add local, remote and SSH hosts through connection-specific fields',async()=>{
  for(const type of ['local','remote','ssh']){
    const ui=harness();ui.button('Add host').props.onClick();
    ui.change('Host ID',type);ui.change('Display name',type+' machine');
    ui.change('Connection type',type);
    if(type==='local')ui.change('Paseo home directory','/tmp/test-paseo');
    else if(type==='remote')ui.change('Daemon address or pairing link','192.0.2.10:6767');
    else ui.change('SSH destination','user@devbox');
    await ui.submit();
    const args=ui.calls[0].args;
    assert.equal(args.action,'add');assert.equal(args.host_id,type);assert.equal(args.enabled,true);
    if(type==='local'){assert.equal(args.home,'/tmp/test-paseo');assert.equal(args.target,undefined);}
    else {assert.equal(args.home,undefined);assert.equal(args.target,type==='ssh'?'ssh://user@devbox':'192.0.2.10:6767');}
  }
});
test('edit keeps identity stable and replaces the connection type',async()=>{
  const ui=harness({hosts:[{id:'worker',label:'Worker',home:'/tmp/paseo',enabled:true}]});
  ui.button('Edit').props.onClick();assert.equal(ui.field('Host ID').props.disabled,true);
  ui.change('Connection type','ssh');ui.change('SSH destination','ssh://user@new-worker');
  await ui.submit();assert.equal(ui.calls[0].args.action,'update');assert.equal(ui.calls[0].args.target,'ssh://user@new-worker');assert.equal(ui.calls[0].args.home,undefined);
});
test('probe, pause, and remove target the selected host',async()=>{
  const ui=harness({hosts:[{id:'worker',target:'worker:6767',enabled:true}]});
  await ui.button('Check connection').props.onClick();
  await ui.button('Pause monitoring').props.onClick();
  await ui.button('Remove').props.onClick();
  assert.deepEqual(ui.calls.map(call=>call.args.action),['probe','update','remove']);
  assert.ok(ui.calls.every(call=>call.args.host_id==='worker'));
  assert.equal(ui.calls[1].args.enabled,false);
});
test('desktop package registers the native settings page and older SDK fallback',()=>{
  let source=fs.readFileSync('desktop/plugin.js','utf8').replace(/^import .*;\n/gm,'').replace('export default {','this.plugin = {');
  for(const modern of [true,false]){
    const pages=[],registrations=[];
    const context={React:{createElement:(type,props)=>({type,props})},host:{onEvent:()=>()=>{}}};
    vm.createContext(context);vm.runInContext(source,context);
    const ctx={register:entry=>registrations.push(entry),onDispose(){}};
    if(modern)ctx.registerSettingsPage=page=>pages.push(page);
    context.plugin.register(ctx);
    const page=modern?pages[0]:registrations.find(entry=>entry.area==='settings.plugins');
    assert.equal(page.title,'Paseo Executive');assert.equal(page.render().props.settings,true);
  }
});
