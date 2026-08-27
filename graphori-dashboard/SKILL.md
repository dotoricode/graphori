---
name: graphori-dashboard
description: Graphori 실행 상태 대시보드를 로컬 브라우저로 연다. 사용자가 Graphori 대시보드, 현재 작업 화면, 특정 run의 진행 상황이나 완료 결과를 열어 달라고 할 때 사용한다. 대시보드 UI 자체를 구현하거나 수정하는 작업에는 사용하지 않는다.
---

# Graphori Dashboard

기존 Graphori 실행 기록을 읽는 로컬 대시보드 서버를 시작하고 해당 화면을 연다.
실행 기록은 읽기만 하며 Graphori 작업을 새로 시작하거나 재개하지 않는다.

## 1. 대상 확정

사용자가 workspace나 run ID를 지정했으면 그대로 사용한다. 지정하지 않았으면 현재
Git 저장소 루트를 workspace로 사용하고, Git 저장소가 아니면 현재 디렉터리를 사용한다.
run ID를 생략하면 Graphori CLI가 journal 수정 시각 기준 가장 최근 작업을 선택한다.

이 단계는 절대 경로의 workspace와 선택적 run ID가 확정되면 완료다.

## 2. 대시보드 시작

`graphori` 명령이 설치되어 있는지 확인한다. 없으면 설치가 필요하다고 보고하고 저장소
내부 스크립트 경로를 추측하지 않는다.

다음 명령을 host가 제공하는 장기 실행 terminal 또는 background process로 시작한다.

```bash
graphori dashboard --root "<workspace>" --port 0
```

특정 작업을 열 때만 `--run-id "<run-id>"`를 추가한다. CLI는 loopback 주소에만
bind하고 실제 URL을 첫 출력으로 제공한다. 서버가 살아 있는 동안 명령이 계속 실행되는
것은 정상이며 timeout이나 멈춤으로 판정하지 않는다.

이 단계는 `Graphori 대시보드: http://127.0.0.1:<port>/...` 출력과 살아 있는 서버
process를 확인하면 완료다.

## 3. 화면 확인

CLI가 브라우저를 자동으로 열지 못하면 출력된 URL을 사용 가능한 브라우저 도구로 연다.
페이지가 응답하고, run ID를 지정했다면 같은 ID가 화면에 표시되는지 확인한다. 화면을
열기 위한 확인만 수행하며 journal, run 상태, gate를 변경하지 않는다.

완료 보고에는 URL, workspace, 선택된 run ID 또는 최근 작업 자동 선택 여부를 적는다.
서버는 사용자가 대시보드를 볼 수 있도록 유지하고, 종료 요청을 받았을 때만 닫는다.
