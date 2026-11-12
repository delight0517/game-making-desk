/* Standalone delivery manager card. Mount <section id="production-manager"></section>.
   Server GET /api/manager and POST /api/manager {action,start/stop/run,minutes,goal}.
   Text-only rendering prevents model/user content becoming executable HTML. */
(() => {
  const mount = document.getElementById('production-manager');
  if (!mount) return;
  const head = document.createElement('div');
  head.style.cssText = 'display:flex;gap:12px;align-items:center;flex-wrap:wrap';
  const title = document.createElement('strong'); title.textContent = '제작 진행 매니저';
  const timer = document.createElement('span'); timer.style.fontVariantNumeric = 'tabular-nums';
  const start = document.createElement('button'); start.textContent = '20분 진행 시작';
  const stop = document.createElement('button'); stop.textContent = '진행 중지';
  const run = document.createElement('button'); run.textContent = '인계된 인트로 Codex 검토';
  head.append(title,timer,start,stop,run);
  const priority = document.createElement('p'), next = document.createElement('p'), notice = document.createElement('p');
  const moduleList = document.createElement('div'), progress = document.createElement('p');
  const list = document.createElement('ol'), workers = document.createElement('div'), error = document.createElement('p');
  error.style.color = 'var(--danger,#e69b8f)';
  const details = document.createElement('details'), summary = document.createElement('summary');
  summary.textContent = '결과물과 완료 기준'; details.append(summary,list);
  mount.append(head,priority,next,notice,progress,moduleList,workers,details,error);
  let active = false;
  function paint(state) {
    const statuses = {'idle':'대기','running':'진행 중','interrupted':'재개 필요','stopped':'중지됨','timebox-ended':'시간 종료 · 확인 필요','completed':'증거 확인 완료'};
    const seconds = state.remainingSeconds;
    timer.textContent = `${statuses[state.status] || state.status}${seconds == null ? '' : ' · '+Math.floor(seconds/60)+':'+String(seconds%60).padStart(2,'0')}`;
    priority.textContent = state.priority || '';
    next.textContent = '다음 작업: ' + (state.nextAction || '진행 시작');
    notice.textContent = state.notice || '';
    const check = state.lastCheckAt ? new Date(state.lastCheckAt*1000).toLocaleTimeString('ko-KR') : '시작 대기';
    const nextCheck = state.nextCheckAt ? new Date(state.nextCheckAt*1000).toLocaleTimeString('ko-KR') : '—';
    progress.textContent = `병렬 실행 ${state.activeCount || 0}/${state.maxParallel || 2} · 실제 결과물 점검 ${check} · 다음 ${nextCheck} · 10분마다 진행 기록`;
    moduleList.replaceChildren();
    for (const module of state.modules || []) {
      const row = document.createElement('div');
      row.style.cssText = 'padding:8px 10px;border:1px solid var(--line);margin:6px 0;border-radius:6px';
      const name = document.createElement('strong'); name.textContent = module.label;
      const status = document.createElement('span');
      status.textContent = ` · ${module.mode === 'single-writer' ? '단일 파일 구현' : '읽기 전용'} · ${module.job?.status || '대기'}`;
      row.append(name,status);
      if (module.job?.result?.summary) {
        const summary = document.createElement('p'); summary.textContent = module.job.result.summary; row.append(summary);
      }
      if (module.job?.resultFile) {
        const link = document.createElement('a'); link.textContent = '실제 응답 보기';
        link.href = '/api/artifact?path='+encodeURIComponent(module.job.resultFile); link.target='_blank'; link.rel='noopener'; row.append(link);
      }
      moduleList.append(row);
    }
    start.disabled = state.status === 'running' || active;
    stop.disabled = !['running'].includes(state.status) || active;
    run.disabled = !state.candidateWriteReady || state.status !== 'running' || active || ['queued','running'].includes(state.job?.status);
    run.title = state.candidateWriteReady ? '명시적으로 인계된 게임 후보 파일 하나만 검토합니다.' : '게임 구현 담당자의 명시적 인계 전에는 겹쳐 쓰지 않습니다.';
    list.replaceChildren();
    for (const stage of state.delivery?.stages || []) {
      const item = document.createElement('li');
      item.textContent = `${stage.complete ? '✓' : '○'} ${stage.label} — ${stage.complete ? '증거 확인' : (stage.missing || []).join(' · ')}`;
      if (stage.caveat) item.textContent += ' / ' + stage.caveat;
      for (const artifact of stage.evidence || []) {
        if (!artifact.path || !/(submission|game-candidate|prologue-media)[\\/].*\.(docx|pdf|mp4|zip|png|html|md)$/i.test(artifact.path)) continue;
        const link = document.createElement('a');
        link.href = '/api/artifact?path=' + encodeURIComponent(artifact.path);
        link.target = '_blank'; link.rel = 'noopener';
        link.textContent = ' ' + artifact.path.split(/[\\/]/).pop();
        link.style.marginLeft = '8px';
        item.append(link);
      }
      list.append(item);
    }
    workers.replaceChildren();
    for (const worker of state.workers || []) {
      const item = document.createElement('p');
      item.textContent = `${worker.task} · ${worker.status} · ${worker.evidence?.length || 0}개 인계 파일`;
      workers.append(item);
    }
    if (state.job) {
      const job = document.createElement('p');
      job.textContent = `Codex 구현 검토: ${state.job.status}${state.job.summary ? ' · '+state.job.summary : ''}`;
      workers.append(job);
    }
    error.textContent = state.job?.error || '';
  }
  async function refresh() {
    try {
      const response = await fetch('/api/manager', {cache:'no-store'});
      if (!response.ok) throw new Error('매니저 서비스 연결 확인 중');
      paint(await response.json());
    } catch (e) { error.textContent = e.message; }
  }
  async function action(name) {
    if (active) return;
    active = true;
    try {
      const response = await fetch('/api/manager', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:name,minutes:20})});
      const state = await response.json();
      if (!response.ok) throw new Error(state.error || '진행 요청 실패');
      paint(state);
    } catch (e) { error.textContent = e.message; }
    finally { active = false; await refresh(); }
  }
  start.onclick = () => action('start'); stop.onclick = () => action('stop'); run.onclick = () => action('run');
  refresh(); setInterval(refresh,3000);
})();
