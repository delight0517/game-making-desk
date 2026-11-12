# Game Making Desk

대화·기획 문서·이미지 스토리보드·제작 진행을 한 로컬 작업실에서 다루는 Windows/Web 앱입니다. MIT 라이선스.

## 빠른 시작

필수: Python 3.10 이상. 브라우저 모드는 별도 pip 패키지 없이 실행합니다.

```powershell
 git clone https://github.com/delight0517/game-making-desk.git
 cd game-making-desk
 python desk/server.py
```

브라우저에서 http://127.0.0.1:8767 을 엽니다. 종료는 서버 터미널에서 Ctrl+C.

### 독립 Windows 앱

.NET 8 SDK와 Microsoft Edge WebView2 Runtime이 필요합니다. NuGet의 Microsoft WebView2 SDK를 빌드 시 다운로드합니다.

```powershell
 pwsh -File ./Build-Windows.ps1
 pwsh -File ./desk/Open-Desk.ps1
```

데스크톱 앱을 다시 빌드할 때는 앱 창을 먼저 닫습니다. 빌드 스크립트는 실행 중인 앱을 강제 종료하지 않습니다. 브라우저 모드만 쓴다면 .NET은 필요 없습니다.

## 기능

- 게임·문서 작업 / 시스템 개선 모드 분리
- 독립적인 4~5개 질문, 관심도 표시, 여러 답안과 수동 편집
- 작성 중인 질문 고정; 서버 수정본은 사용자가 열 때만 적용
- 자동 저장, revision 충돌 검사, 원자적 JSON 교체와 백업
- 이미지·PDF·텍스트 첨부, 이미지 붙여넣기와 삭제/복원
- 이미지 스토리보드: 이동·크기·순서·제목·메모·되돌리기
- Ctrl+Plus/Equals, Ctrl+Minus, Ctrl+0 글자 크기 조절과 저장
- 몰입 대화 화면과 별도 노트 보관
- Codex CLI를 이용한 백그라운드 기획·대화, 중지와 결과 검토
- 마감·산출물 증거·제작 모듈 상태 표시
- Windows 독립 팝업 알림, 창 위치·크기 기억, IME 간섭 완화

## AI 연결과 데이터

일반 노트와 스토리보드는 AI 로그인 없이 사용할 수 있습니다. AI 실행에는 Node.js와 별도로 설치·로그인한 Codex CLI가 필요합니다. 현재 CLI 검색은 Windows의 `%APPDATA%/npm/node_modules/@openai/codex/bin/codex.js`를 사용합니다. 다른 설치 경로·플랫폼에서는 어댑터를 수정해야 합니다.

AI 버튼을 누르면 해당 대화·아이디어·선택된 첨부와 작업 문맥이 사용자의 Codex 제공자로 전달됩니다. 자동 기획은 앱 설정에서 끌 수 있습니다. 제작 매니저의 후보 수정은 명시적 단일 파일 인계와 해시 확인이 필요합니다. **게임 프로젝트·도구가 저절로 설치되거나 모든 제작 단계가 자동 완료되는 시스템은 아닙니다.**

OnlyChat은 선택적 로컬 패널/상태 연결이며, 외부 대화·계정 라우터 통합은 미완성입니다. OnlyChat이나 Claude Code Game Studios를 포함하거나 그 프로젝트에 소속된 배포물이 아닙니다. 기획 양식 참고: https://github.com/Donchitos/Claude-Code-Game-Studios

## 재사용

`desk/questions.json`의 프로젝트명·질문·웨이포인트를 바꾸세요. 샘플 이미지는 생성한 빈 배경이며, 실제 프로젝트 이미지는 포함하지 않았습니다. 사용자 파일은 `desk/answers.json`, `desk/media/`, `desk/backups/`, `desk/*-state.json` 등에 생성되며 Git에서 제외됩니다. WebView2 프로필은 `%LOCALAPPDATA%/GameMakingDesk/WebView2`에 저장됩니다 (`GAME_MAKING_DESK_PROFILE`로 변경 가능).

기존 작업실의 답변·문서·이미지·영상·계정·로그는 이 저장소에 없습니다. 개인 프로젝트 자료를 옮기려면 별도 백업 후 로컬에만 복사하세요.

제작 검증 어댑터는 원래 게임 과제 사례에서 출발했습니다. `desk/delivery.py`, `desk/manager_modules/__init__.py`, `desk/production_manager.py`의 입력 경로와 수락 조건을 프로젝트에 맞게 수정하세요. 게임 엔진·게임 소스·최종 제출물은 제공하지 않습니다.

## 개발과 검사

```powershell
 python -m unittest discover -s tests -v
 node --check desk/desk.js
 node --check desk/immersive.js
 node --check desk/storyboard.js
```

구조와 적용 범위: [ARCHITECTURE.md](ARCHITECTURE.md). 재사용 절차: [REUSE.md](REUSE.md). 의존성: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

실제 한국어 IME 전환·Windows 사용자 클릭·외부 계정/업로드는 별도 환경에서 검증해야 합니다. 테스트용 증거 파일이나 AI의 성공 문구는 실제 플레이/제출 증거가 아닙니다.
