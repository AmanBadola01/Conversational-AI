import {useEffect,useMemo,useRef,useState,type CSSProperties} from 'react';
type EffectMode='light'|'dark';
export type TopologyFieldProps={mode?:EffectMode;hue?:number;saturation?:number;brightness?:number;className?:string;style?:CSSProperties};
export const TOPOLOGY_FIELD_DEFAULTS={mode:'dark',hue:0,saturation:1,brightness:1} as const;
function clamp(n:number,min:number,max:number){return Math.max(min,Math.min(max,Number.isFinite(n)?n:min))}
// CPU projection retains the supplied spherical topology without a nested WebGL
// document. This keeps the decorative background reliable in report hosts.
export default function TopologyField({mode=TOPOLOGY_FIELD_DEFAULTS.mode,hue=0,saturation=1,brightness=1,className,style}:TopologyFieldProps){
 const safeMode:EffectMode=mode==='light'?'light':'dark',light=safeMode==='light';
 const container=useRef<HTMLDivElement>(null),canvas=useRef<HTMLCanvasElement>(null);const [fallback,setFallback]=useState(false);
 const points=useMemo(()=>Array.from({length:120},(_,i)=>{const phi=Math.acos(-1+2*i/120),theta=Math.sqrt(120*Math.PI)*phi;return{x:Math.cos(theta)*Math.sin(phi),y:Math.sin(theta)*Math.sin(phi),z:Math.cos(phi)}}),[]);
 const edges=useMemo(()=>points.flatMap((p,i)=>points.slice(i+1).flatMap((q,j)=>{const distance=Math.hypot(p.x-q.x,p.y-q.y,p.z-q.z);return distance<.45?[{a:i,b:i+j+1,strength:1-distance/.45}]:[]})),[points]);
 useEffect(()=>{
  const host=container.current,target=canvas.current;if(!host||!target)return;const ctx=target.getContext('2d');if(!ctx){setFallback(true);return}setFallback(false);
  let frame=0,time=0,visible=true,disposed=false,last=0,width=1,height=1;const motion=matchMedia('(prefers-reduced-motion: reduce)');
  function render(){if(!ctx)return;ctx.clearRect(0,0,width,height);const angle=time*.0018,cos=Math.cos(angle),sin=Math.sin(angle),radius=Math.min(width,height)*.48,cx=width*(width>768?.69:.55),cy=height*.52;
   const projected=points.map(p=>{const x=p.x*cos+p.z*sin,z=-p.x*sin+p.z*cos,y=p.y*Math.cos(.2)-z*Math.sin(.2),depth=p.y*Math.sin(.2)+z*Math.cos(.2),perspective=2.8/(2.8+depth);return{x:cx+x*radius*perspective,y:cy+y*radius*perspective,z:depth}});
   ctx.strokeStyle=light?'#7e8c73':'#d5d5d5';ctx.lineWidth=.8;
   edges.forEach(edge=>{const p=projected[edge.a],q=projected[edge.b];ctx.globalAlpha=(.18+edge.strength*.5)*(1-(p.z+q.z+2)/7);ctx.beginPath();ctx.moveTo(p.x,p.y);ctx.lineTo(q.x,q.y);ctx.stroke()});
   ctx.fillStyle=light?'#6c7b5f':'#fff';projected.forEach((p,i)=>{const pulse=(Math.sin(time*(.015+(i%7)*.003)+i*2.399)+1)/2;ctx.globalAlpha=.45+pulse*.55;ctx.beginPath();ctx.arc(p.x,p.y,.75+pulse*1.3,0,Math.PI*2);ctx.fill()});ctx.globalAlpha=1;host!.dataset.topologyState='ready';
  }
  function animate(now:number){frame=0;if(disposed||!visible||document.hidden||motion.matches)return;if(now-last>32){time++;render();last=now}frame=requestAnimationFrame(animate)}
  function sync(){cancelAnimationFrame(frame);frame=0;if(!disposed&&visible&&!document.hidden&&!motion.matches)frame=requestAnimationFrame(animate);else if(!disposed)render()}
  function resize(){const rect=host!.getBoundingClientRect();width=Math.max(1,rect.width);height=Math.max(1,rect.height);const ratio=Math.min(devicePixelRatio,2);target!.width=Math.round(width*ratio);target!.height=Math.round(height*ratio);ctx!.setTransform(ratio,0,0,ratio,0,0);render()}
  const size=new ResizeObserver(resize);size.observe(host);const intersection=new IntersectionObserver(entries=>{visible=entries[0]?.isIntersecting!==false;sync()});intersection.observe(host);document.addEventListener('visibilitychange',sync);motion.addEventListener('change',sync);resize();sync();
  return()=>{disposed=true;cancelAnimationFrame(frame);size.disconnect();intersection.disconnect();document.removeEventListener('visibilitychange',sync);motion.removeEventListener('change',sync)};
 },[light,points,edges]);
 const h=clamp(hue,-180,180),s=clamp(saturation,0,2),b=clamp(brightness,.35,1.65),filter=h===0&&s===1&&b===1?undefined:`hue-rotate(${h}deg) saturate(${s}) brightness(${b})`;
 return <div ref={container} className={className} data-mode={safeMode} data-topology-state={fallback?'fallback':undefined} aria-hidden="true" style={{position:'relative',display:'block',width:'100%',height:'100%',overflow:'hidden',background:light?'#f8f8f6':'#070707',pointerEvents:'none',filter,...style}}><canvas ref={canvas} style={{display:fallback?'none':'block',width:'100%',height:'100%'}}/>{fallback&&<svg viewBox="-1.2 -1.2 2.4 2.4" width="100%" height="100%" style={{position:'absolute',inset:0}}>{edges.map(({a,b},i)=><line key={i} x1={points[a].x} y1={points[a].y} x2={points[b].x} y2={points[b].y} stroke={light?'#85927a':'#fff'} strokeWidth=".002" opacity=".5"/>)}</svg>}</div>
}
