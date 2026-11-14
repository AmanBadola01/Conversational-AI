from pathlib import Path
root=Path(__file__).resolve().parent.parent
html=(root/'dist/preview.html').read_text()
start=html.index('<script>\nconst $=')
end=html.index('</script>',start)+len('</script>')
html=html[:start]+html[end:]
start=html.index('<script>\nconst oldForm=')
end=html.index('</script>',start)+len('</script>')
bridge="""<script>
const oldForm=document.getElementById('form');oldForm.hidden=true;
const mount=document.createElement('div');mount.id='react-composer';mount.style.cssText='display:flex;justify-content:center;position:relative;z-index:20';oldForm.before(mount);
const stopButton=document.createElement('button');stopButton.id='stop-response';stopButton.textContent='Stop response';stopButton.hidden=true;stopButton.onclick=()=>stop();mount.after(stopButton);
document.querySelector('.hint').textContent='Enter to send · Shift + Enter for a new line · Backend connected · Text only · Model fallback active';
</script>"""
html=html[:start]+bridge+'<script>'+(root/'integrated.js').read_text()+'</script>'+html[end:]
html=html.replace('● &nbsp; Local preview · v0.1','● Connecting…').replace('<span class="caps muted" style="padding:8px">','<span id="connection-status" class="caps muted" style="padding:8px">')
html=html.replace('All systems local','Backend memory').replace('Context preserved','Persistent memory').replace('428 ms','—')
(root/'dist/integrated.html').write_text(html)
