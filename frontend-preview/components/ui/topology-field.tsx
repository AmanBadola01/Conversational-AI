import {useMemo, type CSSProperties} from 'react';
import threeSource from 'three/build/three.min.js?raw';

type EffectMode = 'light' | 'dark';
type FocusRole = 'background' | 'button' | 'visual';
type FocusTarget = {selector: string; role: FocusRole; fit?: 'cover' | 'contain-square' | 'wide-wordmark' | 'portrait-stage'; preserveTransform?: boolean};
type EffectDefinition = {
  title: string; source: string; background: string; targets: readonly FocusTarget[];
  theme?: {nativeMode?: EffectMode; lightBackground: string; darkBackground: string; invertBackground?: boolean};
  hiddenTargets?: readonly string[];
};
export type TopologyFieldProps = {mode?: EffectMode; hue?: number; saturation?: number; brightness?: number; className?: string; style?: CSSProperties};
export const TOPOLOGY_FIELD_DEFAULTS = {mode: 'dark', hue: 0, saturation: 1, brightness: 1} as const;

// The supplied scene, isolated to its background target. Hidden presentation
// text, stock portraits, Iconify, and Tailwind CDN scripts are unnecessary here.
const topologySource = `<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Nexus Architecture - Topology</title>
<style>html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#070707}canvas{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}</style>
</head><body><canvas id="animationCanvas"></canvas>
<script>${threeSource.replace(/<\/script/gi, '<\\/script')}</script>
<script>
(function(){
const canvas = document.getElementById('animationCanvas');
let renderer;
try { renderer = new THREE.WebGLRenderer({canvas, alpha:true, antialias:true}); }
catch(error) { document.body.dataset.topologyState='fallback'; return; }
let width=innerWidth,height=innerHeight;
const scene=new THREE.Scene();scene.fog=new THREE.Fog(0x0a0a0a,300,950);
const camera=new THREE.PerspectiveCamera(60,width/height,1,2000);camera.position.z=650;
renderer.setPixelRatio(Math.min(devicePixelRatio,2));
const group=new THREE.Group();scene.add(group);
const numNodes=120,nodes=[],nodeGeo=new THREE.SphereGeometry(1,16,16);
for(let i=0;i<numNodes;i++){
 const phi=Math.acos(-1+2*i/numNodes),theta=Math.sqrt(numNodes*Math.PI)*phi;
 const mesh=new THREE.Mesh(nodeGeo,new THREE.MeshBasicMaterial({color:0xffffff,transparent:true,opacity:.9}));
 mesh.position.set(Math.cos(theta)*Math.sin(phi),Math.sin(theta)*Math.sin(phi),Math.cos(phi));
 mesh.userData={baseSize:Math.random()*1.5+1,pulseSpeed:Math.random()*.02+.015,pulseOffset:Math.random()*Math.PI*2};
 group.add(mesh);nodes.push(mesh);
}
const linePos=[],lineColors=[];
for(let i=0;i<numNodes;i++)for(let j=i+1;j<numNodes;j++){
 const dist=nodes[i].position.distanceTo(nodes[j].position),threshold=.45;
 if(dist<threshold){
  linePos.push(nodes[i].position.x,nodes[i].position.y,nodes[i].position.z,nodes[j].position.x,nodes[j].position.y,nodes[j].position.z);
  const alpha=(1-dist/threshold)*.8;lineColors.push(alpha,alpha,alpha,alpha,alpha,alpha);
 }
}
const lineGeo=new THREE.BufferGeometry();lineGeo.setAttribute('position',new THREE.Float32BufferAttribute(linePos,3));lineGeo.setAttribute('color',new THREE.Float32BufferAttribute(lineColors,3));
const lineMat=new THREE.LineBasicMaterial({vertexColors:true,transparent:true,blending:THREE.AdditiveBlending,depthWrite:false,opacity:.65});
group.add(new THREE.LineSegments(lineGeo,lineMat));
let time=0,frame=0;
const motion=matchMedia('(prefers-reduced-motion: reduce)');
function draw(){
 group.rotation.y=time*.0018;group.rotation.x=.2;group.rotation.z=time*.0006;
 nodes.forEach(mesh=>{const p=mesh.userData,pulse=(Math.sin(time*p.pulseSpeed+p.pulseOffset)+1)/2;const scale=(p.baseSize+pulse*1.8)/group.scale.x;mesh.scale.set(scale,scale,scale);mesh.material.opacity=.4+pulse*.6});
 renderer.render(scene,camera);document.body.dataset.topologyState='ready';
}
function resize(){width=Math.max(1,innerWidth);height=Math.max(1,innerHeight);camera.aspect=width/height;camera.updateProjectionMatrix();renderer.setSize(width,height);const R=width>768?380:200;group.scale.set(R,R,R);group.position.set(width>768?width*.2:0,width>768?-height*.05:-height*.2,0);draw()}
function animate(){frame=0;if(document.hidden||motion.matches)return;time++;draw();frame=requestAnimationFrame(animate)}
function sync(){cancelAnimationFrame(frame);draw();if(!document.hidden&&!motion.matches)frame=requestAnimationFrame(animate)}
addEventListener('resize',resize);document.addEventListener('visibilitychange',sync);motion.addEventListener('change',sync);resize();sync();
addEventListener('pagehide',()=>{cancelAnimationFrame(frame);removeEventListener('resize',resize);document.removeEventListener('visibilitychange',sync);motion.removeEventListener('change',sync);nodeGeo.dispose();lineGeo.dispose();lineMat.dispose();nodes.forEach(n=>n.material.dispose());renderer.dispose()},{once:true});
})();
</script></body></html>`;
const EFFECT: EffectDefinition = {title:'Nexus topology field',source:topologySource,background:'#070707',theme:{nativeMode:'dark',lightBackground:'#f8f8f6',darkBackground:'#070707',invertBackground:true},targets:[{selector:'#animationCanvas',role:'background'}]};
function clamp(value:number,minimum:number,maximum:number){return Math.min(maximum,Math.max(minimum,Number.isFinite(value)?value:minimum))}
function effectBackground(definition:EffectDefinition,mode:EffectMode){return definition.theme?.[`${mode}Background`]??definition.background}
function buildFocusedDocument(definition:EffectDefinition,mode:EffectMode){
 const background=effectBackground(definition,mode);
 const invertBackground=definition.theme?.invertBackground===true&&definition.theme.nativeMode!==mode;
 const targetJson=JSON.stringify(definition.targets).replace(/</g,'\\u003c');
 const hiddenTargetJson=JSON.stringify(definition.hiddenTargets??[]).replace(/</g,'\\u003c');
 const backgroundFilter=invertBackground?'filter:invert(1) hue-rotate(180deg) saturate(.92) brightness(1.02)!important;':'';
 const focusStyle=`<style data-threeui-focus>
html,body{width:100%!important;height:100%!important;min-height:0!important;margin:0!important;padding:0!important;overflow:hidden!important;background:${background}!important;color-scheme:${mode}!important}
body{position:relative!important;display:flex!important;align-items:center!important;justify-content:center!important}
body>*{visibility:hidden!important}body[data-threeui-ready]>[data-threeui-role]{visibility:visible!important}
[data-threeui-residual],[data-threeui-hidden]{display:none!important}
[data-threeui-role="background"]{position:fixed!important;inset:0!important;width:100%!important;height:100%!important;max-width:none!important;max-height:none!important;z-index:0!important;opacity:1!important;pointer-events:none!important;${backgroundFilter}}
</style>`;
 const focusScript=`<script data-threeui-focus>(function(){
 document.documentElement.dataset.sfMode=${JSON.stringify(mode)};
 var isolated=false;
 function isolate(){
  if(isolated)return;var roots=[];
  (${hiddenTargetJson}).forEach(function(selector){document.querySelectorAll(selector).forEach(function(element){element.setAttribute('data-threeui-hidden','');element.setAttribute('aria-hidden','true');element.inert=true})});
  (${targetJson}).forEach(function(spec){var element=document.querySelector(spec.selector);if(!element)return;element.setAttribute('data-threeui-role',spec.role);if(spec.fit)element.setAttribute('data-threeui-fit',spec.fit);if(spec.preserveTransform)element.setAttribute('data-threeui-preserve-transform','');if(!roots.some(function(root){return root.contains(element)}))roots.push(element)});
  if(!roots.length)return;isolated=true;roots.forEach(function(root){document.body.appendChild(root)});
  Array.from(document.body.children).forEach(function(element){if(roots.indexOf(element)!==-1)return;element.setAttribute('data-threeui-residual','');element.setAttribute('aria-hidden','true');element.inert=true});
  document.body.setAttribute('data-threeui-ready','');requestAnimationFrame(function(){dispatchEvent(new Event('resize'))});
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',function(){setTimeout(isolate,100)},{once:true});else setTimeout(isolate,100);
 addEventListener('load',isolate,{once:true});
})();</script>`;
 return definition.source.replace(/<\/head>/i,`${focusStyle}</head>`).replace(/<\/body>/i,`${focusScript}</body>`);
}
export default function TopologyField({mode=TOPOLOGY_FIELD_DEFAULTS.mode,hue=0,saturation=1,brightness=1,className,style}:TopologyFieldProps){
 const safeMode:EffectMode=mode==='light'?'light':'dark';
 const background=effectBackground(EFFECT,safeMode);
 const source=useMemo(()=>buildFocusedDocument(EFFECT,safeMode),[safeMode]);
 const h=clamp(hue,-180,180),s=clamp(saturation,0,2),b=clamp(brightness,.35,1.65);
 const filter=h===0&&s===1&&b===1?undefined:`hue-rotate(${h}deg) saturate(${s}) brightness(${b})`;
 return <iframe className={className} data-mode={safeMode} title={EFFECT.title} srcDoc={source} sandbox="allow-scripts" loading="eager" tabIndex={-1} aria-hidden="true" referrerPolicy="no-referrer" style={{display:'block',width:'100%',height:'100%',border:0,background,filter,...style}}/>;
}
