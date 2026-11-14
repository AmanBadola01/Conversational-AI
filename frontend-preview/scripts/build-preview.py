"""Bundle React composer into the existing standalone HTML preview."""
from pathlib import Path
root=Path(__file__).resolve().parent.parent
html=(root/'index.html').read_text()
bootstrap="""<script>(function(){let theme;try{theme=localStorage.getItem('continuum-theme')}catch{}if(theme!=='light'&&theme!=='dark')theme=window.matchMedia?.('(prefers-color-scheme: dark)').matches?'dark':'light';document.documentElement.dataset.continuumTheme=theme;document.documentElement.classList.toggle('dark',theme==='dark');document.documentElement.style.colorScheme=theme})();</script>"""
html=html.replace('<style>',bootstrap+'<style>',1)
css=(root/'dist/style.css').read_text()
js=(root/'dist/chat-input.js').read_text()
bridge='''
const oldForm=document.getElementById('form');
oldForm.hidden=true;
const mount=document.createElement('div');mount.id='react-composer';mount.style.cssText='display:flex;justify-content:center;position:relative;z-index:20';
oldForm.before(mount);
const prefs=oldForm.querySelector('.compose-bottom>div');
// Persona and memory controls now live inside the React input; legacy controls stay hidden.
const stopButton=document.createElement('button');stopButton.textContent='Stop response';stopButton.type='button';stopButton.hidden=true;stopButton.style.cssText='display:block;margin:4px auto;font-size:11px';
mount.after(stopButton);stopButton.onclick=()=>stop();
const syncStop=()=>{window.dispatchEvent(new CustomEvent('continuum:stream',{detail:streaming}));stopButton.hidden=!streaming;stopButton.style.display=streaming?'block':'none'};
new MutationObserver(syncStop).observe(document.getElementById('chainStatus'),{childList:true});syncStop();
window.addEventListener('continuum:selection',e=>{
 const {persona,memoryTechnique}=e.detail;
 const personaControl=document.getElementById('persona');personaControl.value=persona;
 const modeControl=document.getElementById('mode');modeControl.value=memoryTechnique;
 document.querySelector('.pill').textContent=memoryTechnique;
});
window.addEventListener('continuum:submit',e=>{
 if(streaming){toast('Stop the current response before sending another message.');return}
 const {value,meta}=e.detail;
 const files=meta.attachments.map(file=>file.name).join(', ');
 document.getElementById('prompt').value=value+(files?'\\n[Local image attachments: '+files+']':'');
 oldForm.requestSubmit();
 toast(meta.persona+' · '+meta.memoryTechnique+' · simulated response');
});
const hint=document.querySelector('.hint');hint.textContent='Enter to send · Shift + Enter for a new line · Persona and memory selections configure this local demo. Images stay local; the simulator does not analyze them.';
'''
# Tailwind utilities are isolated from the existing workspace's CSS reset.
html=html.replace('</style>', '\n'+css+'\n#form[hidden]{display:none!important}#react-composer{isolation:isolate}#react-composer textarea{margin:0;border:0}#react-composer button{font:inherit}#react-composer .text-xs{font-size:12px}#react-composer .text-sm{font-size:14px}\n</style>',1)
html=html.replace('</html>', '<script>'+bridge+'</script><script>'+js.replace('</script','<\\/script')+'</script></html>')
(root/'dist/preview.html').write_text(html)
print('Standalone preview saved to dist/preview.html')
