# PROCESS.md 가독성 복구 기록

## 원인

`docs/PROCESS.md`를 UTF-8로 확인한 결과 inline HTML/CSS, `color`·`background` 지정, 테마 의존 마크업은 없었습니다. 문서는 일반 Markdown이며 표, 인라인 코드, 링크, 굵은 글씨만 사용합니다. 따라서 흰 배경 탭에서 흰 글씨가 사라지는 현상은 원본 Markdown의 흰색 지정이 아니라 Orca가 `file://` Markdown을 표시할 때 사용하는 렌더러/테마 문제로 판단했습니다.

## 변경

- `docs/PROCESS.md`의 한국어 내용, 진행 사실, `REVISE`·`BLOCKED`·Human Gate 상태는 변경하지 않았습니다.
- `docs/PROCESS_VIEW.html`을 추가했습니다. 같은 폴더의 `PROCESS.md`를 XMLHttpRequest로 읽고, 로컬 JavaScript로 제목·목록·표·링크·인라인 코드·코드 블록을 렌더링하므로 내용 동기화는 PROCESS.md 한 파일 수정으로 충분합니다.
- 외부 CDN과 Google Font를 사용하지 않습니다. 시스템 한국어 글꼴 fallback을 사용합니다.
- CSS를 명시해 배경 `#fff`, 본문/표/코드 `#172033`, 링크 `#0645ad`, 표 테두리 `#66758a`, 코드 배경 `#eef2f7`을 지정했습니다. 일반 본문과 링크·표·코드는 흰 배경에서 WCAG AA 대비를 확보하도록 어두운 색을 사용했습니다.
- 게임형 dashboard는 구현하지 않았습니다.

## 검증

- `PROCESS.md` repo-scoped 검색: inline HTML/CSS 및 색상·테마 지정 없음; Markdown 표·인라인 코드 구조 확인.
- Orca in-app Browser에서 아래 URL을 새 탭으로 열어 확인했습니다:
  - URL: `docs/PROCESS_VIEW.html`
  - Browser page id: `49bf0cf3-4703-4d31-9ebf-1836d28ab5e6`
- 확인 항목: `document.body` computed background/color, `main`의 text 존재, 링크·표·코드의 computed color/background, 표와 제목 렌더링.
- 실제 eval 결과: body background `rgb(255, 255, 255)`, body color `rgb(23, 32, 51)`(`#172033`), 링크 `rgb(6, 69, 173)`(`#0645ad`), 표 글자 `rgb(23, 32, 51)`, 코드 배경 `rgb(238, 242, 247)`, 본문 text 길이 8146.
- `document.title`은 `Graphori 작업 기록`, 본문은 `Graphori 작업 기록`, `마지막 갱신`, `I02 revision-3` 내용을 포함했습니다.
- Orca screenshot도 성공했습니다(현재 열린 탭에서 캡처).

## 열린 탭

- URL: `docs/PROCESS_VIEW.html`
- page id: `49bf0cf3-4703-4d31-9ebf-1836d28ab5e6`
