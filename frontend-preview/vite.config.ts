import { defineConfig } from 'vite';
import tailwindcss from '@tailwindcss/vite';
export default defineConfig({plugins:[tailwindcss()],define:{'process.env.NODE_ENV':JSON.stringify('production')},resolve:{alias:{'@':new URL('.',import.meta.url).pathname}},build:{lib:{entry:'main.tsx',name:'ContinuumInput',cssFileName:'style',formats:['iife'],fileName:()=> 'chat-input.js'},cssCodeSplit:false}});
