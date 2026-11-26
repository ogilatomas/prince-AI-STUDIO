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
// ---- Text to Video: create a real video through the backend ----
const API_URL='https://prince-ai-studio-api.onrender.com';
const MAX_SECONDS=60; // same limit as the backend while we test
const videoButton=document.getElementById('videoGenerate');
const videoButtonLabel=videoButton.innerHTML;
const resultBox=document.getElementById('videoResult');
const resultStep=document.getElementById('resultStep');
const resultPercent=document.getElementById('resultPercent');
const resultBar=document.getElementById('resultBar');
const resultWarnings=document.getElementById('resultWarnings');
const resultDone=document.getElementById('resultDone');
const resultVideo=document.getElementById('resultVideo');
const resultDownload=document.getElementById('resultDownload');

function sleep(ms){return new Promise(resolve=>setTimeout(resolve,ms));}

function showProgress(step,percent,isError){
  resultBox.hidden=false;
  resultStep.textContent=step;
  resultStep.classList.toggle('result-error',!!isError);
  resultPercent.textContent=percent+'%';
  resultBar.style.width=percent+'%';
}

function finishButton(){
  videoButton.disabled=false;
  videoButton.innerHTML=videoButtonLabel;
}

async function readJson(response){
  try{return await response.json();}catch(e){return {};}
}

videoButton.addEventListener('click',async()=>{
  const prompt=document.getElementById('videoPrompt').value.trim();
  if(prompt.length<5){notify('Please describe your video first (at least 5 characters).');return;}

  const chosen=document.querySelector('#videoDurations button.chosen');
  const seconds=Number(chosen?chosen.dataset.seconds:60);
  if(seconds>MAX_SECONDS){notify('While we test the free servers, videos are limited to 1 minute. Please choose 15, 30 or 1 min.');return;}

  const payload={
    prompt:prompt,
    style:document.getElementById('videoStyle').value,
    aspect_ratio:document.getElementById('videoRatio').value.split(' ')[0],
    duration_seconds:seconds,
    voice:document.getElementById('voice').value,
    audio:document.getElementById('audio').value
  };

  videoButton.disabled=true;
  videoButton.textContent='Working...';
  resultDone.hidden=true;
  resultWarnings.hidden=true;
  resultVideo.removeAttribute('src');
  showProgress('Contacting the server (it may need up to a minute to wake up)...',2,false);

  try{
    // 1. Start the job
    const controller=new AbortController();
    const timeout=setTimeout(()=>controller.abort(),90000);
    const startResponse=await fetch(API_URL+'/api/create-video',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(payload),
      signal:controller.signal
    });
    clearTimeout(timeout);
    const started=await readJson(startResponse);
    if(!startResponse.ok){
      const message=typeof started.detail==='string'?started.detail:'The server rejected the request.';
      showProgress(message,0,true);
      notify(message);
      finishButton();
      return;
    }

    // 2. Check progress every 4 seconds
    const jobId=started.job_id;
    let failedChecks=0;
    while(true){
      await sleep(4000);
      let job;
      try{
        const jobResponse=await fetch(API_URL+'/api/jobs/'+jobId);
        job=await readJson(jobResponse);
        if(jobResponse.status===404){
          showProgress('The server restarted and lost this job. Please try again.',0,true);
          finishButton();
          return;
        }
        failedChecks=0;
      }catch(error){
        failedChecks++;
        if(failedChecks>=6){
          showProgress('Lost connection to the server. Please try again.',0,true);
          finishButton();
          return;
        }
        continue;
      }

      showProgress(job.step||'Working...',job.progress||0,false);
      if(job.warnings&&job.warnings.length){
        resultWarnings.textContent='Notice: '+job.warnings.join(' ');
        resultWarnings.hidden=false;
      }

      if(job.status==='failed'){
        showProgress('Failed: '+(job.error||'unknown problem'),0,true);
        notify('The video could not be created.');
        finishButton();
        return;
      }
      if(job.status==='done'){
        const videoUrl=API_URL+'/api/videos/'+jobId;
        resultVideo.src=videoUrl;
        resultDownload.href=videoUrl;
        resultDone.hidden=false;
        showProgress('Your video is ready: '+(job.title||'Untitled'),100,false);
        notify('Your video is ready!');
        finishButton();
        return;
      }
    }
  }catch(error){
    console.error('Video creation problem:',error);
    showProgress('Could not reach the server. Please try again in a minute.',0,true);
    notify('Could not reach the server.');
    finishButton();
  }
});

document.getElementById('clipGenerate').addEventListener('click',()=>{
  const url=document.getElementById('videoUrl').value.trim();
  const file=fileInput.files[0];
  if(!url&&!file){notify('Paste a video link or upload a video first.');return;}
  if(url&&!/^https?:\/\//i.test(url)){notify('Please enter a complete link beginning with https://');return;}
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
