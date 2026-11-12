/* Conversation feature: persistent drafts, server-owned jobs, explicit note transfer. */
(()=>{
 const previous=desk;
 desk=function(){const base=previous(),init=base.init;return {...base,
  immersive:base.storageGet('desk-immersive')==='on',chatDraft:base.storageGet('desk-chat-draft')||'',chat:{messages:[],status:'idle'},chatError:'',chatSending:false,chatNotice:false,chatSeen:'',chatComposing:false,
  async init(){await init.call(this);await this.refreshChat();setInterval(()=>this.refreshChat(),2000)},
  setImmersive(open){this.immersive=!!open;this.storageSet('desk-immersive',open?'on':'off');if(open){this.chatNotice=false;this.chatSeen=this.chat.messages.at(-1)?.id||'';this.storageSet('desk-chat-seen',this.chatSeen)}},
  editChat(){this.storageSet('desk-chat-draft',this.chatDraft)},
  chatRunning(){return ['queued','running'].includes(this.chat.status)},
  async refreshChat(){try{const r=await fetch('/api/chat');if(!r.ok)return;const next=await r.json();this.chat=next;const last=next.messages.at(-1);if(last?.role==='assistant'&&last.id!==this.storageGet('desk-chat-seen')){if(!this.immersive)this.chatNotice=true;else this.storageSet('desk-chat-seen',last.id)}}catch{}},
  async sendChat(){if(this.chatSending||this.chatRunning()||this.chatComposing||!this.chatDraft.trim())return;const text=this.chatDraft;this.chatSending=true;this.chatError='';try{this.chat=await this.post('/api/chat',{text,requestId:crypto.randomUUID(),provider:'codex'});if(this.chatDraft===text){this.chatDraft='';this.editChat()}}catch(e){this.chatError=e.message}finally{this.chatSending=false}},
  async stopChat(){try{this.chat=await this.post('/api/chat/stop',{})}catch(e){this.chatError=e.message}},
  async keepChat(message){if(this.busy||this.dirty){if(this.dirty)await this.save('draft');if(this.busy||this.dirty||this.saveError){this.chatError='현재 노트 저장 후 다시 옮겨 주세요.';return}}try{const fresh=(await(await fetch('/api/desk')).json()).answers;const id='chat-'+message.id;this.state=await this.post('/api/answer',{questionId:this.currentId,answerId:id,text:message.text,status:'draft',revision:fresh.revision});this.chatError='현재 페이지에 별도 메모로 저장했어요. 기존 글은 유지됩니다.'}catch(e){this.chatError=e.message}},
  async planFromChat(message){await this.keepChat(message);if(!this.state.items[this.currentId]?.alternatives?.some(a=>a.id==='chat-'+message.id))return;try{const fresh=(await(await fetch('/api/desk')).json()).answers;this.state=await this.post('/api/answer',{questionId:this.currentId,answerId:'chat-'+message.id,text:message.text,status:'submitted',revision:fresh.revision});this.agent=await this.post('/api/agent',{questionId:this.currentId,provider:'codex'});this.chatError='대화를 기획 작업으로 전달했어요. 다른 대화를 계속할 수 있어요.'}catch(e){this.chatError=e.message}}
 }};
})();
