# I03 + I04 마일스톤 독립 검증

검증 기준은 ADR 0005와 `docs/architecture/EVENT_PROTOCOL.md`의 JSONL single-writer 계약이다. 쉽게 말하면, 여러 생산자는 안전하게 준비 파일을 만들 수 있지만, journal에 최종 기록하는 사람(writer)은 한 명이어야 한다. 이번 검증은 Windows에서 GPT-5.6 Luna medium이 구현과 집중 테스트를 독립적으로 확인한 결과이며, macOS 실행은 아직 모른다(deferred/unknown).

## 실행 명령

```text
python -m unittest discover -s tests -v
Ran 55 tests in 1.482s
OK

python -m compileall -q src tests
```

추가로 소스 파일을 바꾸지 않고 임시 디렉터리에서 15개의 독립 adversarial probe를 실행했다. probe는 두 writer 동시 consume, 같은 timestamp의 ready 순서, exact duplicate, 변경 내용 충돌, event_id 충돌, malformed ready, 마지막 partial line, 중간 줄 손상, `prev_digest`/`digest` 변조, replay projection digest, traversal/absolute path, symlink escape, EvidenceStore filename 무시·내용 충돌, Windows pass + macOS deferred 및 core import를 포함했다.

## 결과

| 경계 | 관찰 결과 | 판정 |
|---|---|---|
| 두 writer 동시 consume | 같은 ready를 두 writer가 읽으면 journal에 같은 사건이 2줄 생길 수 있고 한쪽은 `FileNotFoundError`가 났다 | ADR 범위 밖 제한: single-writer를 지켜야 함 |
| ordering tie | 동일 `mtime_ns`에서 filename tie-break가 재현 가능했다 | 통과 |
| duplicate/conflict | 같은 내용은 `duplicate`, 내용 변경 또는 같은 event_id 충돌은 `conflict`로 격리되고 원 기록은 유지됐다 | 통과 |
| malformed ready | quarantine으로 이동하고 journal에는 쓰지 않았다 | 통과 |
| partial tail / middle corruption | newline 없는 마지막 조각은 quarantine 후 앞부분 복구; 중간 손상은 예외로 fail-closed | 통과 |
| digest chain / replay | `prev_digest` 또는 `digest` 변조는 거부; 같은 journal replay의 projection digest는 동일 | 통과 |
| path boundary | `..`, 절대/drive-relative/UNC는 거부; symlink fixture는 현재 환경에서 권한/지원 부족으로 deferred | 통과·symlink 실행은 unknown |
| EvidenceStore | caller filename은 저장 경로에 쓰이지 않고, 같은 내용은 SHA-256 한 객체로 dedupe됐다 | 통과 |
| platform/import | Windows 결과를 global pass로 올리지 않으며 macOS는 deferred/unknown; 코어 import는 표준 라이브러리와 내부 모듈뿐이다 | 통과 |

다중 writer 결과는 안전하지 않지만, 이는 구현이 보장한다고 주장한 범위를 벗어난다. ADR 0005 7절은 writer를 한 프로세스로 제한하고 writer lease/epoch가 필요한 다중 coordinator를 MVP 밖으로 명시한다. 따라서 이 probe는 P1 결함으로 분류하지 않으며, 운영자는 한 run에 writer 하나만 사용해야 한다. 단일 writer에서의 동시 producer 제출은 전체 테스트와 probe 모두 10건을 빠짐없이 기록했다.

실패한 것처럼 보인 probe 중 path traversal, middle corruption, digest 변조는 “예외가 나야 성공”인 보안 probe였다. 실제 안전 동작이 확인된 것이며, 제품 테스트 55건은 모두 성공했다. 소스·테스트·프로토콜 문서는 수정하지 않았다.

macOS는 실행하지 않았으므로 승인된 macOS 결과가 아니다. 이 문서의 결론은 Windows에서 I03/I04 구현과 ADR 0005 범위가 일치한다는 뜻으로만 해석해야 한다.

VERDICT: APPROVE
