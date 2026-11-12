/* Client update contract: preserve writing state; never wait for user inactivity. */
(()=>{
 const KEY='lava-desk-live-session-v1';let loadedVersion=null,pendingVersion=null,updating=false,imeComposing=false;
 const model=()=>window.Alpine?.$data(document.body);
 function checkpoint(){
  const d=model(),el=document.getElementById('idea');if(!d?.ready||!el)return;
  const focus=document.activeElement;
  const state={questionId:d.currentId,questionSnapshot:d.q,answerId:d.answerId||'main',text:el.value,dirty:d.dirty||el.value!==d.text,revision:d.state.revision,scroll:window.scrollY,editorScroll:el.scrollTop,start:el.selectionStart,end:el.selectionEnd,roundFocus:focus?.dataset?.roundId,roundText:focus?.dataset?.roundId?focus.value:undefined,roundStart:focus?.selectionStart,roundEnd:focus?.selectionEnd,viewRoundId:d.viewRoundId,roundMode:d.roundMode,chatFocus:focus?.id==='chat-input',chatStart:focus?.selectionStart,chatEnd:focus?.selectionEnd,focus:focus===el?'idea':focus?.getAttribute?.('aria-label'),at:Date.now()};
  try{localStorage.setItem(KEY,JSON.stringify(state))}catch{}
  return state;
 }
 async function restore(){
  const d=model();if(!d?.ready){setTimeout(restore,150);return}
  let snap;try{snap=JSON.parse(localStorage.getItem(KEY)||'null')}catch{}if(!snap||!d.brief.questions.some(q=>q.id===snap.questionId))return;
  if(d.editEpoch>0||d.viewEpoch>0)return;
  d.dirty=false;d.setViewMode?.(snap.roundMode===true);if(snap.viewRoundId)d.viewRoundId=snap.viewRoundId;d.loadRound?.();if(snap.questionSnapshot?.id===snap.questionId)d.storageSet('desk-pinned-question:'+snap.questionId,JSON.stringify(snap.questionSnapshot));d.selectQuestion(snap.questionId,'restore');
  if(snap.roundFocus&&typeof snap.roundText==='string'&&Object.hasOwn(d.roundDrafts||{},snap.roundFocus)&&d.roundDrafts[snap.roundFocus]!==snap.roundText){d.roundDrafts[snap.roundFocus]=snap.roundText;d.editRound(snap.roundFocus)}
  const item=d.state.items[snap.questionId];const alt=item?.alternatives?.find(x=>x.id===snap.answerId);const serverText=alt?.text??item?.text??'';
  d.answerId=snap.answerId;
  if(snap.dirty&&snap.text!==serverText){
   if(snap.revision!==d.state.revision){d.answerId='recovered-'+crypto.randomUUID();d.saveLabel='업데이트 전 글을 별도 메모로 복구했어요'}
   d.text=snap.text;d.dirty=true;d.submitted=false;d.storageSet(d.key(),JSON.stringify({text:d.text,baseRevision:d.state.revision}));
   if(!d.conflict)setTimeout(()=>d.save('draft'),400);
  }else{d.text=serverText;d.dirty=false}
  const viewEpoch=d.viewEpoch;
  requestAnimationFrame(()=>requestAnimationFrame(()=>{if(d.viewEpoch!==viewEpoch||d.currentId!==snap.questionId)return;const el=document.getElementById('idea');if(document.hasFocus()&&snap.focus==='idea'){el.focus({preventScroll:true});el.setSelectionRange(Math.min(snap.start||0,el.value.length),Math.min(snap.end||0,el.value.length))}el.scrollTop=snap.editorScroll||0;window.scrollTo(0,snap.scroll||0);if(document.hasFocus()&&snap.chatFocus&&d.immersive){const chatEl=document.getElementById('chat-input');chatEl?.focus({preventScroll:true});chatEl?.setSelectionRange(snap.chatStart||0,snap.chatEnd||0)}if(document.hasFocus()&&snap.roundFocus){const roundEl=Array.from(document.querySelectorAll('[data-round-id]')).find(x=>x.dataset.roundId===snap.roundFocus);if(roundEl){roundEl.focus({preventScroll:true});roundEl.setSelectionRange(snap.roundStart||0,snap.roundEnd||0)}}}));
 }
 async function versionCheck(){
  if(localStorage.getItem('desk-live-updates')==='off')return;
  if(updating)return;
  try{
   const r=await fetch('/api/client-version');if(!r.ok)return;const data=await r.json();
   if(loadedVersion===null){loadedVersion=data.version;return}
   if(data.version===loadedVersion)return;
   if(pendingVersion!==data.version){pendingVersion=data.version;return}
   const d=model();if(!d?.ready)return;
   // Finish only the current IME composition, not the whole writing session.
   if(d.composing||d.chatComposing||imeComposing)return;
   updating=true;checkpoint();d.saveLabel='화면 업데이트 중 · 글과 위치를 복원합니다';
   if(d.dirty&&!d.busy&&!d.conflict)await d.save('draft');
   checkpoint();window.deskUpdateInProgress=true;location.reload();
  }catch{updating=false}
 }
 document.addEventListener('compositionstart',()=>{imeComposing=true},true);
 document.addEventListener('compositionend',()=>{imeComposing=false;checkpoint()},true);
 document.addEventListener('input',checkpoint,true);
 document.addEventListener('keyup',checkpoint,true);
 document.addEventListener('selectionchange',()=>{if(document.activeElement?.id==='idea')checkpoint()});
 window.addEventListener('pagehide',checkpoint);
 window.addEventListener('beforeunload',checkpoint);
 window.deskPrepareUpdate=checkpoint;
 document.addEventListener('DOMContentLoaded',()=>{restore();versionCheck();setInterval(versionCheck,4000);setInterval(checkpoint,2000)});
})();
