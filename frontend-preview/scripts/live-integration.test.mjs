import {JSDOM,VirtualConsole} from 'jsdom';
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
const base=process.env.PREVIEW_URL||'http://127.0.0.1:20305';
const email=`live-${Date.now()}@example.com`;
const registration=await fetch(base+'/api/auth/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:'Live QA',email,password:'live-test-password'})});
assert.equal(registration.status,201,await registration.clone().text());
const auth=await registration.json();
const authFetch=(url,opts={})=>fetch(new URL(url,base),{...opts,headers:{...opts.headers,Authorization:'Bearer '+auth.access_token}});
const errors=[];const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));
const dom=new JSDOM(readFileSync(new URL('../dist/integrated.html',import.meta.url),'utf8'),{url:base,runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){w.fetch=authFetch;w.TextDecoder=TextDecoder;w.AbortController=AbortController;w.ResizeObserver=class{observe(){}disconnect(){}};w.HTMLCanvasElement.prototype.getContext=()=>null}});
const w=dom.window,d=w.document;
async function until(check){for(let n=0;n<300;n++){if(check())return;await new Promise(r=>setTimeout(r,100))}throw new Error('Timeout: '+d.querySelector('#toast').textContent)}
await until(()=>d.querySelector('#connection-status').textContent.includes('Connected'));
// Create and clean up only the test-owned conversation.
const prior=w.localStorage.getItem('continuum-conversation');
d.querySelector('#new').click();await until(()=>w.localStorage.getItem('continuum-conversation')!==prior);
const id=w.localStorage.getItem('continuum-conversation');
try{
await until(()=>d.querySelector('#react-composer button'));
const opener=d.querySelector('[aria-label="Open prompt input"]');if(opener)opener.click();
await until(()=>d.querySelector('#react-composer textarea'));
w.dispatchEvent(new w.CustomEvent('continuum:selection',{detail:{persona:'General Assistant',memoryTechnique:'Hybrid memory'}}));
w.dispatchEvent(new w.CustomEvent('continuum:submit',{detail:{value:'Integration check: project Cedar has a launch budget of 12000 dollars.',meta:{attachments:[]}}}));
await until(()=>d.querySelector('#chainStatus').textContent==='Generating');
await until(()=>d.querySelector('fieldset').disabled);
await until(()=>d.querySelector('#chainStatus').textContent==='Idle');
assert.equal(d.querySelectorAll('.msg').length,2,'UI error: '+d.querySelector('#toast').textContent);
assert(d.querySelectorAll('.bubble')[1].textContent.length>0);
const saved=await authFetch(`${base}/api/conversations/${id}`).then(r=>r.json());assert.equal(saved.messages.length,2);assert.equal(saved.memory_type,'hybrid');
await until(()=>!d.querySelector('fieldset').disabled);
assert(d.querySelector('#tokens').textContent!=='2,486');
d.querySelector('[data-view="memory"]').click();assert(!d.querySelector('#other').classList.contains('hidden'));
const theme=d.querySelector('#theme-control button');theme.click();await until(()=>d.documentElement.dataset.continuumTheme==='dark');
assert.equal(errors.length,0,errors.join('\n'));
console.log('PASS: UI mount, live connection, conversation creation, SSE, busy state, saved history, tokens, memory view, theme.');
}finally{await authFetch(`${base}/api/conversations/${id}`,{method:'DELETE'});dom.window.close()}
