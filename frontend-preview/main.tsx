import React,{useEffect,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {PromptInput} from '@/components/ui/ai-chat-input';
import './index.css';
import TopologyField from '@/components/ui/chat-topology-field';
import {initialTheme,applyTheme,type Theme} from '@/lib/theme';
applyTheme(initialTheme());
function useTheme(){const [theme,setTheme]=useState<Theme>(initialTheme);useEffect(()=>{const listener=(e:Event)=>setTheme((e as CustomEvent<Theme>).detail);window.addEventListener('continuum:theme',listener);return()=>window.removeEventListener('continuum:theme',listener)},[]);return theme}
function ThemeToggle(){const theme=useTheme();return <button type="button" aria-label={theme==='dark'?'Switch to light theme':'Switch to dark theme'} title={theme==='dark'?'Switch to light theme':'Switch to dark theme'} aria-pressed={theme==='dark'} onClick={()=>applyTheme(theme==='dark'?'light':'dark',true)}>{theme==='dark'?'☀':'☾'}</button>}
function Background(){const theme=useTheme();return <TopologyField mode={theme}/>}
function Composer(){const [busy,setBusy]=useState(false);const [settings,setSettings]=useState<{personas:string[];persona:string;memoryTechnique:string}|null>(null);useEffect(()=>{const listener=(e:Event)=>setSettings((e as CustomEvent).detail);window.addEventListener('continuum:settings',listener);return()=>window.removeEventListener('continuum:settings',listener)},[]);useEffect(()=>{const listener=(e:Event)=>setBusy((e as CustomEvent<boolean>).detail);window.addEventListener('continuum:stream',listener);return()=>window.removeEventListener('continuum:stream',listener)},[]);return <fieldset disabled={busy} aria-label="Chat composer" style={{display:'contents'}}><PromptInput key={settings?.persona+String(settings?.memoryTechnique)} personas={settings?[settings.persona,...settings.personas.filter(p=>p!==settings.persona)]:undefined} memoryTechniques={settings?[settings.memoryTechnique,...["Buffer memory","Summary memory","Entity memory","Knowledge graph"].filter(m=>m!==settings.memoryTechnique)]:undefined} maxAttachments={0} placeholder={busy?'Generating response…':'Where should we take this next?'} onSelectionChange={selection=>window.dispatchEvent(new CustomEvent('continuum:selection',{detail:selection}))} onSubmit={(value,meta)=>window.dispatchEvent(new CustomEvent('continuum:submit',{detail:{value,meta}}))}/></fieldset>}
const target=document.getElementById('react-composer');
if(target)createRoot(target).render(<Composer/>);

const chatMain=document.querySelector<HTMLElement>('.main');
if(chatMain){const background=document.createElement('div');background.id='chat-topology-background';background.setAttribute('aria-hidden','true');chatMain.prepend(background);createRoot(background).render(<Background/>);}

const toolbar=document.querySelector('.toolbar');if(toolbar){const control=document.createElement('span');control.id='theme-control';toolbar.prepend(control);createRoot(control).render(<ThemeToggle/>)}
