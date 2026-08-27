# I08 단계 검증 보고서

## 결론: APPROVE

I08은 승인합니다. Windows에서 실제로 다시 실행했고, GitHub의 push와 pull_request도 확인했습니다. macOS도 GitHub의 실제 macOS runner에서 성공했지만, 이것은 그 runner에서 확인한 범위만 뜻합니다.

## 어린이도 이해할 수 있는 요약

CI는 코드를 올릴 때 자동으로 시험하는 로봇입니다.

- Windows Python 3.11과 3.12에서 unittest 118개가 모두 통과했습니다.
- compileall, dashboard finite smoke, skill validator, evidence manifest도 모두 통과했습니다.
- macOS runner에서는 portable, core, adapter, dashboard, process supervisor의 5개 fixture가 모두 통과했습니다.
- 실패한 fixture를 억지로 PASS라고 바꾸는 코드는 없었습니다.
- 증거 파일에는 사용자 컴퓨터 경로, 사용자 이름, secret/token/password/api key 값이 없었습니다.

## 독립 probe

독립 probe 32개를 실행했습니다. workflow trigger/permissions, Windows 3.11/3.12 matrix, macOS runner, unit/contract, dashboard finite smoke, 고유 artifact 이름, evidence hash, JSON/Markdown schema, platform × fixture × verdict × evidence_id, 실패 전파, secret 및 absolute path/env value 제거, path traversal, UTF-8을 점검했습니다.

결과는 32개 중 32개 기준을 충족했습니다. Windows artifact는 Windows 도구가 만드는 CRLF 줄바꿈이고 UTF-8로 읽혔으며, macOS artifact는 LF였습니다. 줄바꿈 차이는 기록했으며 내용 손상이나 비밀값 노출은 없었습니다.

## 로컬 결과

| 검사 | 결과 |
|---|---|
| `python -m unittest discover -s tests -v` | PASS, 118/118 |
| `python -m compileall -q src tests scripts graphori` | PASS |
| `python scripts/dashboard_smoke.py` | PASS, finite HTTP |
| `python graphori/scripts/validate_skill.py graphori` | PASS |
| evidence generator Windows manifest | PASS, 5 records |

## GitHub 확인

확인한 head SHA는 `e3cbfd8343ad2350e26dab9641c8988ab21c03dc`입니다.

- push run: [31324875529](https://github.com/dotoricode/graphori/actions/runs/31324875529), success
- pull_request run: [31324877422](https://github.com/dotoricode/graphori/actions/runs/31324877422), success
- 각 run의 모든 job conclusion: success
- runner labels: Windows `windows-latest` 3.11/3.12, macOS `macos-latest`
- job IDs: push macOS `93273535554`, Windows 3.12 `93273535565`, Windows 3.11 `93273535568`; PR macOS `93273541277`, Windows 3.11 `93273541294`, Windows 3.12 `93273541301`

두 run 모두 Windows 3.11, Windows 3.12, macOS artifact가 업로드됐습니다. artifact 크기는 Windows evidence JSON+Markdown+digest 묶음 1252 bytes, macOS 묶음 923 bytes였고, 만료일은 각각 2026-11-07입니다. 별도 임시 폴더에 다운로드해 실제 파일을 검사했고 `<home>`, `<workspace>`, `TOKEN`, `SECRET`, `PASSWORD`, `API_KEY`가 없었습니다.

macOS 성공은 `runner_actual` 범위의 증거입니다. 모든 macOS 제품·모든 macOS 버전이 보장된다는 뜻으로 확대하지 않습니다.

## 진행률

I08 승인으로 PROCESS 진행률을 **8/9 = 88.9%**로 올립니다. 다음 단계 I09는 별도 독립 검증으로 남겨 둡니다.
