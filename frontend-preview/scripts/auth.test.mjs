import {JSDOM} from 'jsdom';
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
const {window:w}=new JSDOM(readFileSync('../login/index.html','utf8'),{url:'http://localhost/login/',runScripts:'outside-only'});
const calls=[];
w.fetch=async(url,opts)=>{calls.push({url,opts});return {ok:false,json:async()=>({detail:'Incorrect email or password.'})}};
w.eval(readFileSync('../login/preview.js','utf8'));
for(const mode of ['signup','login']){
 w.document.querySelector(`[data-mode=${mode}]`).click();
 const f=w.document.querySelector(`#${mode}-form`);
 assert.equal(f.checkValidity(),false);
 for(const input of f.querySelectorAll('input'))input.value=input.type==='number'?'123':input.type==='email'?'test@example.com':'test-password';
 f.dispatchEvent(new w.Event('submit',{cancelable:true}));
 await new Promise(r=>setTimeout(r,0));
 assert.match(f.querySelector('.status').textContent,/Incorrect/);
 assert.equal(f.elements.password.value,'');
 const call=calls.at(-1);assert.equal(call.url,`/api/auth/${mode==='signup'?'register':'login'}`);
 assert.equal(call.opts.credentials,'same-origin');
 const data=JSON.parse(call.opts.body);assert.equal(data.email,'test@example.com');
 if(mode==='signup'){assert.equal(data.profile_number,'123');assert.equal(data.username,'test-password');}
}
assert.equal(w.localStorage.length,0);
console.log('PASS: both auth forms, validation, complete payload mapping, error feedback, credential clearing, no browser storage');
