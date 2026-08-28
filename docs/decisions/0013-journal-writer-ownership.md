# Run journal writer ownership

## 결정

canonical `journal.jsonl`을 변경하는 `JournalWriter`는 Run별 `journal/.writer.lock`에
POSIX `flock(LOCK_EX | LOCK_NB)`를 확보한 프로세스 하나만 사용할 수 있다. lock 파일의
존재는 ownership이 아니다. inode를 남겨 두고 OS lock으로만 ownership을 표현한다.

## 이유

두 writer가 동시에 기존 journal head를 읽으면 같은 `seq` 또는 `prev_digest`를 기준으로
서로 다른 line을 append할 수 있다. append 자체가 atomic처럼 보이더라도 hash chain은
손상된다. 따라서 recovery와 journal head 로드는 lock 획득 뒤에만 수행한다.

## 수명과 복구

정상 Run 종료 시 Engine과 CLI는 writer를 닫아 lock을 반환한다. process crash에서는
운영체제가 flock을 자동 해제하므로 다음 writer가 같은 journal을 열어 기존 truncated-tail
recovery를 수행할 수 있다. 지원하지 않는 OS 또는 `flock`을 제공하지 않는 Python에서는
fail-closed하며 한국어 오류로 실행을 중단한다.

## 검증 경계

회귀 fixture는 repository의 `.graphori`를 사용하지 않는다. 임시 repository에서 별도
Python 프로세스로 owner, contender, crash를 실행해 동일 Run 독점, 다른 Run 병렬, crash
뒤 재획득, byte 보존 및 replay digest 일치를 확인한다. POSIX `flock` fixture이므로
비-POSIX host에서는 해당 실제 fixture가 skip되고 writer 생성 자체가 fail-closed한다.
