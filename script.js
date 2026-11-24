const pages = document.querySelectorAll('.page');
const navItems = document.querySelectorAll('.nav-item');
function showPage(name){
  pages.forEach(p=>p.classList.toggle('active',p.id===name));
  navItems.forEach(n=>n.classList.toggle('active',n.dataset.page===name));
  window.scrollTo({top:0,behavior:'smooth'});
}
navItems.forEach(n=>n.addEventListener('click',()=>showPage(n.dataset.page)));
document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>showPage(b.dataset.go)));

function setupDurations(id){
  const root=document.getElementById(id);
  root.querySelectorAll('button').forEach(btn=>btn.addEventListener('click',()=>{
    root.querySelectorAll('button').forEach(x=>x.classList.remove('chosen'));
    btn.classList.add('chosen');
  }));
}
setupDurations('videoDurations'); setupDurations('clipDurations');

const templates = document.querySelectorAll('.template-card');
const overlay=document.getElementById('captionOverlay');
const templateName=document.getElementById('templateName');
const templateCopy={
  bold:{name:'Bold captions',html:'<span>THIS IS</span><mark>IMPORTANT!</mark>',cls:''},
  minimal:{name:'Minimal',html:'<span>A new beginning</span>',cls:'minimal'},
  karaoke:{name:'Karaoke',html:'<span>Follow <mark>your</mark> dream</span>',cls:'karaoke'},
  highlight:{name:'Highlighted words',html:'<span>Make it <mark>HAPPEN</mark></span>',cls:'highlight'}
};
templates.forEach(btn=>btn.addEventListener('click',()=>{
  templates.forEach(x=>x.classList.remove('selected')); btn.classList.add('selected');
  const t=templateCopy[btn.dataset.template]; overlay.innerHTML=t.html; overlay.className='caption-overlay '+t.cls;
  templateName.textContent=t.name;
}));

const fileInput=document.getElementById('videoFile');
fileInput.addEventListener('change',()=>{
  document.getElementById('fileName').textContent=fileInput.files[0]?.name || 'MP4, MOV and other supported formats';
});

const toast=document.getElementById('toast');
let toastTimer;
function notify(message){
  toast.textContent=message; toast.classList.add('show');
  clearTimeout(toastTimer); toastTimer=setTimeout(()=>toast.classList.remove('show'),3800);
}
document.getElementById('videoGenerate').addEventListener('click',()=>{
  const prompt=document.getElementById('videoPrompt').value.trim();
  if(!prompt){notify('Please describe the video you want to create first.');return;}
  notify('Design preview only: connect the AI video-generation backend to create this video.');
});
document.getElementById('clipGenerate').addEventListener('click',()=>{
  const url=document.getElementById('videoUrl').value.trim();
  const file=fileInput.files[0];
  if(!url&&!file){notify('Paste a video link or upload a video first.');return;}
  if(url&&!/^https?:\\/\\//i.test(url)){notify('Please enter a complete link beginning with https://');return;}
  notify('Design preview only: connect the clip-processing and speech-to-text services to generate clips.');
});


// Hook editor preview (AI hook generation requires the future backend).
const hookText=document.getElementById('hookText');
const hookPreviewText=document.getElementById('hookPreviewText');
const hookEnabled=document.getElementById('hookEnabled');
const hookEmojis=document.getElementById('hookEmojis');
function refreshHookPreview(){
  const fallback='😱 WAIT… YOU NEED TO SEE WHAT HAPPENS NEXT! 👀';
  let value=hookText.value.trim()||fallback;
  if(!hookEmojis.checked) value=value.replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/gu,'').replace(/\s{2,}/g,' ').trim();
  hookPreviewText.textContent=hookEnabled.checked?value:'Hook is turned off';
  hookPreviewText.parentElement.style.opacity=hookEnabled.checked?'1':'.5';
}
hookText.addEventListener('input',refreshHookPreview);
hookEnabled.addEventListener('change',refreshHookPreview);
hookEmojis.addEventListener('change',refreshHookPreview);
