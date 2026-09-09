'use strict';
// 실제 콘솔 스크립트를 간단한 DOM 대역에서 실행하여 상태 전이와 판정 계산을 검증한다.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
class Element {
 constructor(){this.value='';this.children=[];this.dataset={};this.tagName='DIV';this.disabled=false;this.hidden=false;}
 append(...values){this.children.push(...values);}
 replaceChildren(...values){this.children=[...values];}
 setAttribute(key,value){this[key]=value;}
 click(){if(this.onclick&&!this.disabled)this.onclick({});}
 requestSubmit(){if(this.onsubmit)this.onsubmit({preventDefault(){}});}
}
const elements=new Map(),choices=['left','right','tie'].map(choice=>{const e=new Element();e.dataset.choice=choice;return e;});
const document={getElementById(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id);},createElement(){return new Element();},querySelector(){return this.getElementById('sides');},querySelectorAll(){return choices;},addEventListener(){}};
const storage=new Map();
const context=vm.createContext({document,console,Date,Math,Map,Set,JSON,Number,String,Error,crypto:{randomUUID:()=> 'test-session'},localStorage:{setItem:(k,v)=>storage.set(k,v),getItem:k=>storage.get(k)},Blob:class{},URL:{createObjectURL:()=>'',revokeObjectURL(){}},setTimeout:fn=>fn()});
vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),context);
function run(code){return vm.runInContext(code,context);}
run(`pairs=validatePairs([{pair_id:'X-Y',left:'Y',right:'X'},{pair_id:'X-Z',left:'X',right:'Z'},{pair_id:'Y-Z',left:'Z',right:'Y'}]); for(const letter of ['X','Y','Z'])bundles.set(letter,validateBundle({letter,files:[{path:'src/a.txt',content:'<script>표시 전용</script>'}]}));ready();start('initial',pairs.map(p=>({...p})));`);
assert.throws(()=>run(`validatePairs([{pair_id:'A-B',left:'실제 라벨',right:'B'}])`));
assert.throws(()=>run(`validateBundle({letter:'X',files:[{path:'../private',content:''}]})`));
run(`$('verdictForm').requestSubmit()`);
assert.equal(run('session.verdicts.length'),0);
for(let d=1;d<=5;d++){
 assert.equal(run('dimension'),d);
 run(`$('advance').onclick()`);
 assert.equal(run('dimension'),d);
 for(let p=0;p<3;p++){
  run(`selected('left');$('reason').value='근거가 읽힘';$('confidence').value='3';$('verdictForm').requestSubmit();`);
 }
 assert.equal(run(`$('verdictForm').hidden`),true);
 assert.equal(run('session.verdicts.length'),d*3);
 run(`$('advance').click()`);
}
assert.equal(run('dimension'),6);
assert.equal(run(`$('rejudge').disabled`),false);
const initial=run('JSON.stringify(session)');
run(`$('rejudge').click()`);
assert.equal(run('session.mode'),'rejudge');
assert.equal(run('activePairs.length'),1);
assert.equal(run(`activePairs[0].left===pairs.find(p=>p.pair_id===activePairs[0].pair_id).right`),true);
assert.equal(run('JSON.stringify(previous)'),initial);
for(let d=1;d<=5;d++){
 run(`selected('right');$('reason').value='동일 후보가 우세';$('confidence').value='2';$('verdictForm').requestSubmit();$('advance').click();`);
}
assert.equal(run(`reversalRows(previous,session).every(r=>r[1]==='0/1 (0.0%)')`),true);
run(`session.verdicts[0].choice='left'`);
assert.equal(run('reversalRows(previous,session)[0][1]'),'1/1 (100.0%)');
run(`session.verdicts[0].choice='tie'`);
assert.equal(run('reversalRows(previous,session)[0][1]'),'1/1 (100.0%)');
run(`session.verdicts[0].choice='right';persist();session=null;activePairs=[];dimension=1;cursor=0;$('restore').onclick();`);
assert.equal(run('dimension'),6);
assert.equal(run('session.verdicts.length'),5);
run(`session=null;dimension=1;cursor=0;$('rejudge').onclick();`);
assert.equal(run('session.mode'),'rejudge');
assert.equal(run('session.verdicts.length'),0);
run(`localStorage.setItem=()=>{throw new Error('차단')};persist();`);
assert.equal(run(`$('status').className`),'error');
console.log('통과: 차원 순서 강제 · 필수 이유 · 30% 좌우 교환 · 동률 포함 뒤집힘 보정 · 세션 복구 · 저장 차단 처리');
