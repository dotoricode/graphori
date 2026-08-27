# I02 portable Python stdlib core 구현 보고서

## 설계 연결

Stage 2 acceptance와 `GRAPHORI_ARCHITECTURE.md`, `EVENT_PROTOCOL.md`,
`PORTABILITY_CONTRACT.md`, ADR 0001~0004를 기준으로 portable core를 구현했다.
Core는 Python 3.11 표준 라이브러리만 사용하며 Orca/Claude/OpenAI SDK, OS별
프로세스 API, 외부 패키지를 import하지 않는다. `requires`/`requires_gate`만
scheduling DAG로 검사하고 `rework_of`는 history edge로 취급한다.

구현된 계약은 다음과 같다.

- canonical enum과 Task/Attempt/Verdict/Liveness/Usage/PlatformVerdict 모델
- ADR 0004 공식에 따른 결정적 risk score와 hard trigger 기반 Fast/Standard/Critical 선택
- Fast(automatic), Standard(targeted), Critical(normal + adversarial independent verifier,
  fan-in verifier, Human Gate) topology 생성
- 동일 attempt verifier 및 동일 실행 identity/provider/model/checkout 독립성 금지
- REVISE 3회까지 revision, 4번째부터 Human Gate escalation
- task transition guard와 event reducer
- usage unknown을 `None`으로 보존하고 0으로 환산하지 않음
- Windows `pass`와 macOS `deferred`/`unknown`이 한 projection에 공존하는 partial scope

## 파일

- `src/graphori_core/models.py`: canonical enum/data model
- `src/graphori_core/compiler.py`: risk compiler, DAG validation, topology, independence,
  revision limit, transition guard
- `src/graphori_core/reducer.py`: verdict/platform event reducer
- `src/graphori_core/__init__.py`: public API
- `tests/test_core.py`: unittest contract fixtures
- `pyproject.toml`: Python 3.11+ 최소 setuptools 구성

`docs/PROCESS.md`와 journal/dashboard/adapters는 수정하지 않았다.

## 실행 명령 및 실제 결과

실행 명령:

```text
python -m unittest discover -s tests -v
```

실제 결과:

```text
......
----------------------------------------------------------------------
Ran 6 tests in 0.002s.

OK
```

검증 fixture는 세 모드, scheduling cycle과 history edge, Critical verifier 독립성 및
동일 attempt 거부, REVISE 4번째 escalation, usage unknown, Windows/macOS partial
platform scope를 각각 확인한다.
