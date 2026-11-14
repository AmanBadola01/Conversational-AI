import React,{useEffect,useState} from 'react';
import {createRoot} from 'react-dom/client';
import TopologyField from '@/components/ui/topology-field';
type Theme='light'|'dark';
function currentTheme():Theme{return document.documentElement.dataset.continuumTheme==='light'?'light':'dark'}
function LoginBackground(){
 const [theme,setTheme]=useState<Theme>(currentTheme);
 useEffect(()=>{
  const listener=()=>setTheme(currentTheme());
  window.addEventListener('continuum:theme',listener);
  listener();
  return()=>window.removeEventListener('continuum:theme',listener);
 },[]);
 return <TopologyField mode={theme}/>;
}
const target=document.getElementById('login-topology-background');
if(target)createRoot(target).render(<LoginBackground/>);
