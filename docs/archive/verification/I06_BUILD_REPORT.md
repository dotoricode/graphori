# I06 화면 구현 보고서

## 쉬운 요약

I06 화면은 검은 터미널 HUD 모양으로 만들었습니다. 화면은 `snapshot`을 먼저 읽고, 그 다음 실제 SSE(`/runs/{run_id}/events`)를 연결합니다. 진행률은 서버가 준 검증 완료 숫자만 보여 주며 heartbeat만으로 숫자가 올라가지 않습니다.

## 화면에 보이는 것

- 연결 상태: connected, stale, blocked
- 검증 결과: pending, PASS, APPROVE 등
- 완료 / 계획 / 남은 일과 근거 기반 progress bar
- 마지막 event 번호와 현재 시각
- node를 팀 카드로 보여 주는 현재 일, liveness, verdict
- stale 또는 idle일 때 멈추는 타이핑 커서와 activity motion

## 실행

PowerShell에서 저장소 루트에 들어가 다음을 실행합니다.

```powershell
$env:PYTHONPATH = "src"
python scripts/dashboard_server.py --root . --port 8765
```

브라우저에서 `http://127.0.0.1:8765/`를 엽니다. 서버는 Python 표준 라이브러리만 사용합니다.

## 확인 결과

- Windows 전체 unittest: 통과
- `python -m compileall -q src tests`: 통과
- localhost snapshot smoke: 통과

이 보고서는 독립 verifier 확인 전 초안입니다. 제품 전체 진행률 표시는 **5/9**로 유지합니다. macOS와 실제 브라우저의 독립 확인은 아직 남았습니다.
