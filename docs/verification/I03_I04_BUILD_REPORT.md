# I03 + I04 구현 보고서

> 작성자: 구현 담당자 1명(단독). 이 보고서는 자체 점검 결과이며 승인(approve)이
> 아니다. [ADR 0005](../decisions/0005-mvp-simple-single-verifier.md)에 따라
> 이번 milestone 완료 뒤 별도 확인자가 스케줄될 수 있다.

## 1. 12살도 이해하는 설명

이번에 만든 건 "공책 쓰는 규칙"이다. 여러 일꾼(producer)이 동시에 사건을
적으려고 하면 종이가 겹쳐서 엉망이 될 수 있다. 그래서 각자 작은 임시 봉투
(`inbox/tmp`)에 먼저 쓰고, 다 쓴 봉투만 진짜 우편함(`inbox/ready`)으로
옮긴다. 그리고 딱 한 명의 "기록 담당자"(writer)만 우편함을 열어서 순서
번호(seq)를 매기고, 진짜 공책(journal.jsonl)에 옮겨 적는다.

같은 편지가 두 번 오면("나 다시 보냈어") 무시한다. 그런데 편지 봉투(ID)는
같은데 내용이 다르면("어? 이거 위조야?") 진짜 공책에는 안 넣고 따로
"수상한 편지함"(quarantine)에 넣는다. 원래 있던 편지는 절대 안 지운다.

공책이 갑자기 잘린 마지막 줄(정전처럼 도중에 멈춘 것)은 그 잘린 부분만
수상한 편지함으로 옮기고, 그 앞의 멀쩡한 부분은 그대로 믿고 쓴다. 하지만
중간 줄이 이상하면(일부러 바꿔치기한 것처럼) 그건 훨씬 심각한 문제라서
전체를 멈추고 사람에게 알린다(조용히 넘어가지 않는다).

증거(evidence)는 내용의 지문(SHA-256 해시)으로만 이름을 붙인다. 누가
"이 파일 이름은 안전해"라고 말해도 믿지 않고, 항상 내용을 다시 확인해서
이름을 만든다.

## 2. 무엇을 만들었나

새 파일(모두 `src/graphori_core` 아래, 외부 라이브러리 없이 표준 라이브러리만
사용):

- `paths.py`: run root 밖으로 못 나가게 막는 안전한 경로 함수. `..`,
  절대 경로, `\\서버\공유` 같은 UNC, 대소문자만 다른 이름 충돌, symlink/junction
  탈출을 모두 막는다.
- `journal.py`: `inbox/tmp -> inbox/ready` 원자적 이동, 단일 writer,
  `seq`/`recorded_at`/`prev_digest`/`digest` 부여, 중복/충돌 판정, 손상된
  파일 격리(quarantine), 잘린 마지막 줄 복구, replay(다시 읽어서 검증).
- `evidence.py`: 내용 해시로만 이름 붙이는 증거 저장소(`EvidenceStore`).

기존 `models.py`, `reducer.py`, `compiler.py`(I02 core)는 그대로 재사용했고
두 번째 "진짜 상태 저장소"를 새로 만들지 않았다. `journal.py`는 event 모양을
검사할 때 `reducer.py`의 `validate_event_envelope`와 `EVENT_TYPES`를 그대로
가져다 쓴다.

## 3. 테스트 (모두 표준 `unittest`, `tests/` 아래)

| 파일 | 확인하는 것 |
|---|---|
| `test_core.py` (기존) | I02 reducer 상태 전이, usage known/estimate/unknown, platform verdict 등 32개 |
| `test_journal_concurrency.py` | 서로 다른 producer 10개가 동시에 제출 → 10개 모두 정확히 한 번씩 기록 |
| `test_journal_ordering.py` | 같은 준비물(ready set)이면 항상 같은 순서로 처리됨(결정적) |
| `test_journal_idempotency.py` | 완전히 같은 편지는 무시, ID는 같은데 내용 다른 편지는 격리하고 원본은 안 바뀜 |
| `test_journal_malformed.py` | 깨진 JSON, 필드 빠짐, run_id 틀림, 모르는 event 종류는 모두 격리 |
| `test_journal_replay.py` | 같은 journal을 두 번 다시 읽어도 같은 해시 체인/같은 projection 결과 |
| `test_journal_recovery.py` | 마지막 줄이 잘렸으면 앞부분은 살리고 뒷부분만 격리, 중간 줄이 손상되면 전체를 멈춤(fail-closed) |
| `test_paths_security.py` | `..` 탈출, 절대/UNC 경로, 대소문자 충돌, **실제 Windows junction 탈출**(관리자 권한 없이도 성공) |
| `test_evidence_store.py` | 내용 해시로만 저장, 이상한 이름을 줘도 저장 경로에 안 씀, 같은 내용은 중복 저장 안 함 |
| `test_platform_and_failure_contract.py` | windows=pass + macos=deferred가 전체 성공으로 합쳐지지 않음, 실패한 node가 있으면 절대 자동으로 성공(PASS)이 되지 않음, usage known/estimate/unknown 구분 |

## 4. 실행한 명령과 결과 (Windows, `python -m unittest`)

```
> python -m unittest discover -s tests -v
...
Ran 55 tests in 3.674s
OK
```

전체 55개 테스트 모두 통과했다(기존 32개 + 새로 만든 23개).

```
> python -m compileall -q src tests
```

경고나 에러 없이 통과했다(문법 오류 없음).

```
> (격리된 임시 폴더로 graphori_core 소스만 복사)
> python -I -c "import sys; sys.path.insert(0,'.'); import graphori_core; ..."
import OK from isolated dir, no repo on sys.path
submodules OK
```

`pip install`은 이 환경에서 인터넷이 막혀 있어(`--no-index`) `setuptools`
빌드 백엔드를 새로 받지 못해 실패했다. 그래서 같은 목적(외부 저장소 경로 없이,
의존성 없이 import되는지)을 확인하는 더 엄격한 대안으로, `graphori_core`
소스만 완전히 새 폴더에 복사한 뒤 `python -I`(격리 모드, 사용자 site-packages도
무시)로 import를 확인했다. 저장소 자체는 `sys.path`에 없었고, import는
성공했다. 이는 외부 dependency가 0개라는 사실을 그대로 보여준다.

```
> python -m unittest test_journal_concurrency test_journal_recovery \
    test_journal_idempotency test_journal_replay   (tests/ 폴더 안에서 실행)
Ran 7 tests in 2.496s
OK
```

동시성/복구 핵심 시나리오만 다시 뽑아 실행한 결과도 통과했다.

## 5. 확인한 것 (acceptance 대조)

- [x] producer 10개 동시 제출 → 서로 다른 이벤트 10개 모두 정확히 기록
- [x] 결정적 ready 순서 (같은 파일 집합 → 같은 처리 순서, 다시 실행해도 동일)
- [x] 정확히 같은 중복은 무시, ID는 같은데 내용이 다르면 `idempotency_conflict`로
      격리하고 원래 기록은 절대 덮어쓰지 않음
- [x] 깨진 ready 파일은 격리
- [x] replay가 해시 체인을 검증하고 같은 projection digest를 재구성함
      (기존 reducer를 재사용해서 두 번 replay한 결과가 완전히 같음을 확인)
- [x] 마지막 줄이 잘려도 앞부분은 보존, 잘린 부분만 격리
- [x] 중간 줄이 손상되면 조용히 넘어가지 않고 전체를 fail-closed로 막음
- [x] 경로 탈출(`..`), 절대 경로, 대소문자 충돌, **실제 Windows junction 탈출**을
      모두 막음(관리자 권한 필요 없이 실제 fixture로 확인함 — "deferred"가
      아니라 실제 통과)
- [x] EvidenceStore가 SHA-256 내용 주소 방식이고 manifest를 가지며, 안전하지
      않은 이름을 줘도 저장 경로에 절대 쓰지 않음
- [x] 기존 reducer 상태 전이, usage known/estimate/unknown 유지(별도 진리 저장소를
      새로 만들지 않음)
- [x] windows=pass + macos=deferred/unknown이 전체 성공(succeeded)으로 축약되지
      않음
- [x] 실패 fixture(failed/blocked/rejected/inconclusive/cancelled)가 자동으로
      PASS(succeeded)로 승격되지 않음

## 6. 하지 않은 것 / 남은 한계

- **macOS는 여전히 `deferred/unknown`이다.** 이번 작업은 Windows에서만
  실행했다. symlink 테스트도 Windows junction만 실제로 확인했고, POSIX symlink는
  macOS 실행 환경이 없어 시험하지 못했다.
- **여러 coordinator/여러 writer 동시 append는 다루지 않는다.** 계약 문서
  (`EVENT_PROTOCOL.md` 7절)대로 "writer lease/epoch가 필요한 다중 coordinator는
  MVP 범위 밖"이라는 결정을 그대로 따랐다. 이번 구현은 단일 writer 프로세스
  전제다.
- **stage5(범용 terminal adapter/ProcessSupervisor), stage6(dashboard),
  stage7(Orca adapter), stage8(GitHub Actions)는 만들지 않았다.** 요청받은
  범위(I03+I04)만 구현했다.
- **cross-device(다른 디스크/파일시스템) tmp→ready 이동은 다루지 않는다.**
  `os.replace`는 같은 파일시스템 안에서만 원자적이라는 계약 문서 5절 6항의
  전제를 그대로 따른다.
- 자체 점검(self-check)일 뿐 독립 검증(approve)이 아니다. ADR 0005에 따라
  이 milestone은 "의미 있는 마일스톤 완료"에 해당하므로, 이 보고서 이후 별도
  확인자가 스케줄될 수 있다.

## 7. 진행률

acceptance(위 5절)가 모두 통과했으므로 승인된 구현 단계 진행률을
**4/9 = 44.4%**(I01, I02, I03, I04)로 `docs/PROCESS.md`에 기록했다. macOS는
여전히 `deferred/unknown`이며 이 보고서는 그 상태를 바꾸지 않는다.
