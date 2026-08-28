# 문서 가독성 뷰어 독립 검증 보고서

검증 날짜: 2026-08-10 (Asia/Seoul)  
검증 브랜치: `feat/mvp-demo-i05-i08`  
대상: `docs/DOCS_VIEWER.html`, `docs/PROCESS_VIEW.html`, `tests/test_docs_viewer.py`, `docs/PROCESS.md`

## 결론

**VERDICT: REVISE**

컴퓨터로 한 안전성 검사와 자동 테스트는 모두 통과했다. 하지만 이 검증은 실제 화면도 확인해야 하는데, 이번 실행 환경에서는 Orca 인앱 브라우저를 사용할 수 없었다. 그래서 화면이 정말 읽기 좋은지 확인하지 못했으며, 확인하지 못한 것을 통과라고 말하지 않는다.

## 어린이도 이해할 수 있는 요약

이 뷰어는 문서를 보여주는 창문이다. 창문은 흰색이고 글자는 진한 색이어야 글을 쉽게 읽을 수 있다. 또 나쁜 사람이 `..`, `C:\`, `http://` 같은 주소를 넣어 문서 폴더 밖의 파일을 읽지 못하게 해야 한다.

코드를 읽어 보니 뷰어는 흰색(`#ffffff`) 배경과 진한 글자(`#172033`)를 정해 두었고, 제목·표·코드·링크·목록을 위한 모양도 있다. 긴 코드나 긴 문장도 화면 밖으로 삐져나가지 않도록 줄을 바꾸게 되어 있다. `PROCESS_VIEW.html`은 같은 기능을 다시 만들지 않고 공용 뷰어로 이동한다.

## 실행한 검사

- Windows 명령 `python -m unittest discover -s tests -v`: **78개 통과, 실패 0개**
- Windows 명령 `python -m compileall -q .`: **통과**
- 독립 경로 probe: **24개** (허용 3개, 거부 21개)

### 독립 probe 결과

허용된 정상 상대 경로:

- `PROCESS.md`
- `verification/I02_CORE_BUILD_REPORT_LUNA.md`
- `a/b/c/deep_file-name.md`

거부된 위험하거나 잘못된 경로:

- `../PROCESS.md`, `../../etc/passwd.md`, `verification/../../../secret.md`
- `/PROCESS.md`, `//PROCESS.md`
- `C:/Windows/system.ini`, `C:\Windows\system.ini`, `\\server\share\secret.md`
- `file:///etc/passwd`, `http://evil.example/x.md`, `https://evil.example/x.md`
- `javascript:alert(1)`, `data:text/html,<script>1</script>`
- `..%2f..%2fsecret.md`, `verification%2fI02.md`, `PROCESS.md%00.txt`
- `PROCESS.txt`, `PROCESS.MD`, `a//b.md`, `a b.md`, `a<TAB>b.md`

## 화면 검증 상태

다음 두 주소를 Orca 인앱 브라우저에서 실제로 열려고 했지만, 현재 환경에서 인앱 브라우저 연결이 `Browser is not available: iab`로 거부되었다.

- `docs/DOCS_VIEWER.html?file=verification/I02_CORE_BUILD_REPORT_LUNA.md`
- `docs/PROCESS_VIEW.html`

따라서 본문 표시, 실제 computed background가 `#fff` 계열인지, text가 `#172033` 계열인지, 제목·표·코드·링크·긴 줄이 화면에서 읽히는지는 **미확인**이다. `docs/PROCESS.md`의 기존 기록도 이 화면 검증이 남아 있다고 적고 있어, 이번 결과는 그 기록과 일치한다.

## 다음에 할 일

Orca 인앱 브라우저가 연결되는 환경에서 위 두 주소를 다시 열고 실제 화면을 확인해야 한다. 본문이 보이고 색과 줄바꿈이 괜찮다는 증거가 남으면 이 단계의 verdict를 다시 판단할 수 있다.
