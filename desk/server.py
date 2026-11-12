"""Loopback-only writing desk. No external packages or AI/provider calls."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit, parse_qs
import argparse
import json
import os
import threading
import base64
import hashlib
import mimetypes
import shutil
import uuid
import urllib.request
from agent_bridge import AgentBridge
from chat_bridge import ChatBridge
from adaptive import interaction_profile
from delivery import evaluate_delivery
from production_manager import ProductionManager

ROOT = Path(__file__).resolve().parent
LOCK = threading.Lock()
BRIDGE = None
CHAT = None
MANAGER = None


def read_json(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        pass
    backups = sorted((ROOT / 'backups').glob('*-' + path.name), reverse=True) if (ROOT / 'backups').exists() else []
    for backup in backups:
        try:
            data = json.loads(backup.read_text(encoding='utf-8'))
            data['_recoveredFrom'] = backup.name
            return data
        except (OSError, ValueError):
            continue
    if path.exists():
        raise ValueError('저장 파일이 손상되었고 읽을 수 있는 백업이 없습니다. 원본을 보존했습니다.')
    return default


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backups = ROOT / 'backups'
        backups.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        shutil.copy2(path, backups / (stamp + '-' + path.name))
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('w', encoding='utf-8') as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temp, path)
    snapshots = ROOT / 'backups'
    snapshots.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    shutil.copy2(path, snapshots / (stamp + '-' + path.name))


def brief_hash():
    return hashlib.sha256((ROOT / 'questions.json').read_bytes()).hexdigest()


def state_read():
    return read_json(ROOT / 'answers.json', {'revision': 0, 'items': {}, 'history': [], 'attachments': []})


def delivery_brief():
    brief = read_json(ROOT / 'questions.json', {})
    delivery = evaluate_delivery(ROOT)
    for original, checked in zip(brief.get('waypoints', []), delivery['stages']):
        original['status'] = checked['status']
        original['evidence'] = ('실제 증거 확인 완료' if checked['complete'] else ' / '.join(checked['missing'])) + (' · '+checked.get('caveat','') if checked.get('caveat') else '')
    brief['nextAction'] = delivery['nextAction']
    return brief, delivery


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, status, value, mime='application/json; charset=utf-8'):
        body = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def valid_host(self):
        return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}

    def do_GET(self):
        if not self.valid_host():
            return self.send(403, {'error': '허용되지 않은 주소입니다.'})
        route = urlsplit(self.path).path
        if route == '/api/manager':
            return self.send(200, MANAGER.snapshot())
        if route == '/api/delivery':
            return self.send(200, evaluate_delivery(ROOT))
        if route == '/api/artifact':
            name = parse_qs(urlsplit(self.path).query).get('path', [''])[0]
            candidate = Path(name)
            if not candidate.is_absolute():
                candidate = ROOT / candidate
            candidate = candidate.resolve()
            allowed_roots = [ROOT / name for name in ('submission', 'prologue-media', 'game-candidate')]
            manager_state = MANAGER.snapshot()
            reports = [module.get('job') or {} for module in manager_state.get('modules', [])]
            report_paths = {Path(job['resultFile']).resolve() for job in reports if job.get('resultFile')}
            allowed_report = candidate in report_paths and candidate.is_relative_to(ROOT/'manager-runs') and candidate.suffix == '.json'
            allowed_artifact = any(candidate.is_relative_to(base) for base in allowed_roots) and candidate.suffix.lower() in ('.docx','.pdf','.mp4','.zip','.png','.html','.md')
            if not (allowed_report or allowed_artifact) or not candidate.is_file():
                return self.send(404, {'error':'등록된 결과물만 열 수 있습니다.'})
            return self.send(200, candidate.read_bytes(), mimetypes.guess_type(str(candidate))[0] or 'application/octet-stream')
        if route == '/api/capabilities':
            return self.send(200, {'version':'0.2.0','multiAnswer':True,'sceneNavigation':True})
        if route == '/api/client-version':
            digest=hashlib.sha256()
            for name in ('index.html','desk.js','live-update.js','immersive.js','production-manager.js'):
                digest.update((ROOT/name).read_bytes())
            return self.send(200, {'version':digest.hexdigest()})
        if route == '/':
            return self.send(200, (ROOT / 'index.html').read_bytes(), 'text/html; charset=utf-8')
        if route in ('/alpine.min.js', '/desk.js', '/live-update.js', '/immersive.js', '/production-manager.js'):
            return self.send(200, (ROOT / route[1:]).read_bytes(), 'text/javascript; charset=utf-8')
        if route == '/reference-doc-cover.png' or route in {f'/doc-image-{i}.png' for i in range(14)}:
            return self.send(200, (ROOT / route[1:]).read_bytes(), 'image/png')
        if route.startswith('/media/'):
            media_id = route.split('/')[-1]
            with LOCK:
                item = next((x for x in state_read().get('attachments', []) if x['id'] == media_id and not x.get('deleted')), None)
                if not item:
                    return self.send(404, {'error': '이미지를 찾지 못했습니다.'})
                return self.send(200, (ROOT / 'media' / item['file']).read_bytes(), item['mime'])
        if route == '/api/chat':
            with LOCK:
                return self.send(200, CHAT.snapshot())
        if route == '/api/desk':
            try:
                with LOCK:
                    brief, delivery = delivery_brief()
                    return self.send(200, {'brief': brief, 'delivery':delivery, 'briefHash': brief_hash(), 'answers': state_read(), 'adaptation': interaction_profile(state_read()), 'agent': BRIDGE.snapshot() if BRIDGE else {'status':'idle'}, 'connections': {'codex': bool(shutil.which('codex.cmd') or shutil.which('codex')), 'onlychat': BRIDGE.onlychat if BRIDGE else False}})
            except (OSError, ValueError):
                return self.send(500, {'error': '저장 파일을 읽을 수 없습니다. 기존 파일을 확인해 주세요.'})
        return self.send(404, {'error': '페이지가 없습니다.'})

    def do_POST(self):
        if not self.valid_host():
            return self.send(403, {'error': '허용되지 않은 주소입니다.'})
        origin = self.headers.get('Origin')
        if origin not in {f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'}:
            return self.send(403, {'error': '이 작업판에서만 저장할 수 있습니다.'})
        if self.path not in ('/api/answer', '/api/skip', '/api/media', '/api/media/delete', '/api/brief', '/api/schedule', '/api/draft', '/api/agent', '/api/agent/stop', '/api/chat', '/api/chat/stop', '/api/manager'):
            return self.send(404, {'error': '잘못된 요청입니다.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length <= 0 or length > 12_000_000:
                return self.send(413, {'error': '첨부 이미지는 8MB 이내로 저장해 주세요.'})
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                return self.send(400, {'error': '입력 형식이 올바르지 않습니다.'})
            if self.path == '/api/manager':
                try:
                    action = data.get('action')
                    if action == 'start': result = MANAGER.start(minutes=data.get('minutes',20))
                    elif action == 'stop': result = MANAGER.stop()
                    elif action == 'run': result = MANAGER.run_candidate()
                    else: raise ValueError('알 수 없는 관리자 요청입니다.')
                    return self.send(200, result)
                except ValueError as error:
                    return self.send(400, {'error':str(error)})
            if self.path == '/api/chat':
                try:
                    return self.send(202, CHAT.send(data.get('text'),data.get('requestId'),data.get('provider','codex')))
                except ValueError as error:
                    return self.send(400, {'error':str(error)})
            if self.path == '/api/chat/stop':
                return self.send(200, CHAT.stop())
            if self.path == '/api/schedule':
                minutes=data.get('minutes')
                if not isinstance(minutes,(int,float)) or isinstance(minutes,bool) or not 1<=minutes<=1440:
                    return self.send(400, {'error':'1분부터 24시간 사이로 설정해 주세요.'})
                started=datetime.fromisoformat(data['startedAt'].replace('Z','+00:00')) if data.get('startedAt') else datetime.now(timezone.utc)
                if started.tzinfo is None:return self.send(400, {'error':'시작 시각에 시간대가 필요합니다.'})
                with LOCK:
                    brief=read_json(ROOT/'questions.json',{})
                    weights=[5,10,10,15,15,5];elapsed=0;plan=[]
                    for i,step in enumerate(brief.get('waypoints',[])):
                        elapsed+=weights[i] if i<len(weights) else 0
                        plan.append({'waypoint':i+1,'label':step['label'],'budgetMinutes':minutes*(weights[i]/60) if i<len(weights) else 0,'dueAt':(started+timedelta(minutes=minutes*elapsed/60)).isoformat()})
                    brief['deadline']={'startedAt':started.isoformat(),'deadlineAt':(started+timedelta(minutes=minutes)).isoformat(),'durationMinutes':minutes,'plan':plan,'rule':'Time never marks work complete. Actual artifacts and checks control waypoint status.'}
                    write_json(ROOT/'questions.json',brief)
                    return self.send(200,{'deadline':brief['deadline']})
            if self.path == '/api/skip':
                with LOCK:
                    state = state_read()
                    brief = read_json(ROOT / 'questions.json', {})
                    qid = data.get('questionId')
                    if qid not in {q['id'] for q in brief['questions']}:
                        return self.send(400, {'error':'질문을 찾지 못했습니다.'})
                    if data.get('revision') != state['revision']:
                        return self.send(409, {'error':'기록이 바뀌었습니다. 새로고침해 주세요.'})
                    events = state.setdefault('interactionEvents', [])
                    if not events or events[-1].get('type') != 'skip' or events[-1].get('questionId') != qid:
                        events.append({'type':'skip','questionId':qid,'at':datetime.now(timezone.utc).isoformat()})
                    state['revision'] += 1
                    write_json(ROOT / 'answers.json', state)
                    job = BRIDGE.start(qid, '사용자가 이 질문을 명시적으로 건너뛰었습니다. 답은 미정입니다. 기획 내용을 발명하거나 기존 작성 초안을 확정하지 마세요. 다음 질문의 형식과 주제를 바꿔 주세요.', 'codex')
                    return self.send(200, {'answers':state,'agent':job,'adaptation':interaction_profile(state)})
            if self.path == '/api/draft':
                with LOCK:
                    if data.get('jobId') != BRIDGE.job.get('id') or not isinstance(data.get('text'),str) or not BRIDGE.job.get('result'):
                        return self.send(409, {'error':'기획 초안이 변경되었습니다. 현재 결과를 다시 확인해 주세요.'})
                    BRIDGE.job['result']['draft'] = data['text']
                    BRIDGE.job['manualEdit'] = True
                    BRIDGE.persist()
                    return self.send(200, BRIDGE.snapshot())
            if self.path == '/api/agent/stop':
                return self.send(200, BRIDGE.cancel())
            if self.path == '/api/agent':
                if data.get('provider') not in ('codex', 'onlychat'):
                    return self.send(400, {'error':'지원하지 않는 연결입니다.'})
                with LOCK:
                    item = state_read()['items'].get(data.get('questionId'))
                    if not item or item['status'] != 'submitted':
                        return self.send(400, {'error':'먼저 답변을 저장해 주세요.'})
                    alternatives = item.get('alternatives', [])
                    group = [{'id':x['id'],'text':x['text']} for x in alternatives if x.get('text','').strip()]
                    idea = ('여러 아이디어 후보입니다. 서로 대안이거나 함께 사용할 수 있습니다. 하나로 확정하거나 임의로 합치지 말고 각각 보존해서 검토하세요.\n'+json.dumps(group,ensure_ascii=False)) if group else item['text']
                    result = BRIDGE.start(data['questionId'], idea, data['provider'])
                return self.send(202, result)
            if self.path == '/api/brief':
                with LOCK:
                    if data.get('briefHash') != brief_hash():
                        return self.send(409, {'error':'다른 작업에서 질문이 수정됐습니다. 새로고침 후 편집해 주세요.'})
                    brief = read_json(ROOT / 'questions.json', {})
                    question = next((q for q in brief['questions'] if q['id'] == data.get('questionId')), None)
                    if not question or not all(isinstance(data.get(k), str) and 0 < len(data[k]) <= 10000 for k in ('title','question')):
                        return self.send(400, {'error':'제목과 질문을 입력해 주세요.'})
                    question['title'], question['question'] = data['title'], data['question']
                    write_json(ROOT / 'questions.json', brief)
                    return self.send(200, {'brief':brief,'briefHash':brief_hash()})
            if self.path in ('/api/media', '/api/media/delete'):
                with LOCK:
                    state = state_read()
                    if data.get('revision') != state['revision']:
                        return self.send(409, {'error':'다른 화면에서 기록이 바뀌었습니다. 새로고침해 주세요.'})
                    attachments = state.setdefault('attachments', [])
                    if self.path.endswith('/delete'):
                        item = next((x for x in attachments if x['id'] == data.get('id')), None)
                        if not item:
                            return self.send(404, {'error':'이미지를 찾지 못했습니다.'})
                        item['deleted'] = not item.get('deleted', False)
                    else:
                        brief = read_json(ROOT / 'questions.json', {})
                        if data.get('questionId') not in {q['id'] for q in brief['questions']}:
                            return self.send(400, {'error':'질문을 확인해 주세요.'})
                        raw = base64.b64decode(data.get('base64',''), validate=True)
                        if not raw or len(raw) > 8 * 1024 * 1024:
                            return self.send(413, {'error':'이미지는 8MB 이내여야 합니다.'})
                        ext, mime = None, None
                        if raw.startswith(b'\x89PNG\r\n\x1a\n'): ext, mime = 'png','image/png'
                        elif raw.startswith(b'\xff\xd8\xff'): ext, mime = 'jpg','image/jpeg'
                        elif raw.startswith((b'GIF87a',b'GIF89a')): ext, mime = 'gif','image/gif'
                        elif raw.startswith(b'RIFF') and raw[8:12] == b'WEBP': ext, mime = 'webp','image/webp'
                        elif raw.startswith(b'%PDF-'): ext, mime = 'pdf','application/pdf'
                        elif str(data.get('name','')).lower().endswith(('.txt','.md')):
                            try:
                                raw.decode('utf-8')
                                ext, mime = 'txt','text/plain; charset=utf-8'
                            except UnicodeDecodeError:
                                pass
                        if not ext:
                            return self.send(400, {'error':'이미지, PDF, UTF-8 TXT/MD를 첨부해 주세요.'})
                        media_id = uuid.uuid4().hex
                        folder = ROOT / 'media'; folder.mkdir(exist_ok=True)
                        name = media_id + '.' + ext
                        with (folder / name).open('xb') as file:
                            file.write(raw); file.flush(); os.fsync(file.fileno())
                        attachments.append({'id':media_id,'file':name,'name':str(data.get('name','image'))[:200],'mime':mime,'questionId':data['questionId'],'deleted':False})
                    state['revision'] += 1
                    write_json(ROOT / 'answers.json', state)
                    return self.send(200, state)
            if not isinstance(data, dict) or not isinstance(data.get('text'), str) or data.get('status') not in ('draft', 'submitted'):
                return self.send(400, {'error': '입력 형식이 올바르지 않습니다.'})
            with LOCK:
                brief = read_json(ROOT / 'questions.json', {})
                if data.get('questionId') not in {q['id'] for q in brief.get('questions', [])}:
                    return self.send(400, {'error': '현재 작업판에 없는 질문입니다.'})
                state = state_read()
                if data.get('revision') != state['revision']:
                    return self.send(409, {'error': '다른 화면에서 답변이 바뀌었습니다. 내 글을 복사한 뒤 새로고침해 주세요.'})
                if data['status'] == 'submitted' and not data['text'].strip():
                    return self.send(400, {'error': '아이디어를 적은 뒤 전달해 주세요.'})
                now = datetime.now(timezone.utc).isoformat()
                answer_id = data.get('answerId', 'main')
                if not isinstance(answer_id,str) or not answer_id or len(answer_id)>80:
                    return self.send(400, {'error':'답안 ID가 올바르지 않습니다.'})
                prior = state['items'].get(data['questionId'], {})
                alternatives = prior.get('alternatives', [])
                if not alternatives and prior.get('text'):
                    alternatives = [{'id':'main','text':prior['text'],'status':prior.get('status','draft'),'updatedAt':prior.get('updatedAt',now)}]
                entry = {'id':answer_id,'text':data['text'],'status':data['status'],'updatedAt':now}
                found = next((i for i,x in enumerate(alternatives) if x['id']==answer_id), None)
                if found is None: alternatives.append(entry)
                else: alternatives[found] = entry
                item = {'questionId': data['questionId'], 'text': data['text'], 'status': data['status'], 'updatedAt': now, 'alternatives':alternatives, 'activeAnswerId':answer_id, 'priority':data.get('priority',prior.get('priority','normal'))}
                if data['status'] == 'submitted':
                    state['history'].append(dict(item))
                    state.setdefault('interactionEvents', []).append({'type':'answer','questionId':data['questionId'],'length':len(data['text'].strip()),'at':now})
                state['items'][data['questionId']] = item
                state['revision'] += 1
                write_json(ROOT / 'answers.json', state)
                return self.send(200, state)
        except (ValueError, TypeError, KeyError):
            return self.send(400, {'error': '저장 요청을 읽을 수 없습니다.'})
        except OSError:
            return self.send(500, {'error': '파일 저장에 실패했습니다. 글을 복사해 보관해 주세요.'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8767)
    parser.add_argument('--data-dir', type=Path, default=ROOT)
    parser.add_argument('--manager-deadline')
    parser.add_argument('--candidate-handoff-sha256')
    args = parser.parse_args()
    ROOT = args.data_dir.resolve()
    BRIDGE = AgentBridge(ROOT, LOCK, read_json, write_json)
    CHAT = ChatBridge(ROOT, LOCK, read_json, write_json)
    MANAGER = ProductionManager(ROOT, read_json, write_json)
    for worker in read_json(ROOT/'manager-worker-intake.json', {}).get('workers', []):
        MANAGER.record_worker(worker['task'], worker['status'], worker['invocation'], worker.get('evidence', []))
    if args.manager_deadline:
        MANAGER.start(deadline=args.manager_deadline)
    if args.candidate_handoff_sha256:
        MANAGER.release_candidate(args.candidate_handoff_sha256)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'Game Making Desk: http://127.0.0.1:{server.server_port}', flush=True)
    server.serve_forever()
