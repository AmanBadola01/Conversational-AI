import {defineConfig} from 'vite';
export default defineConfig({
 define:{'process.env.NODE_ENV':JSON.stringify('production')},
 resolve:{alias:{'@':new URL('.',import.meta.url).pathname}},
 build:{outDir:'../login/assets',emptyOutDir:true,lib:{entry:'login-background.tsx',name:'ContinuumLoginBackground',formats:['iife'],fileName:()=> 'login-background.js'}}
});
