# I01 수정 보고서

작성일: 2026-08-09 (Asia/Seoul)

## 변경 전 문제

- `graphori/agents/openai.yaml`이 CP949 바이트와 CRLF 줄바꿈으로 저장되어 macOS/Linux의 UTF-8 읽기에서 깨질 수 있었습니다.
- `graphori/scripts`에 실제 검사기가 없었습니다.
- `graphori/assets`가 비어 있어 폴더가 저장소에 남는다는 표시가 없었습니다.
- 공식 `quick_validate.py`는 Windows 기본 CP949 환경에서 UTF-8 파일을 읽지 못할 수 있어 `PYTHONUTF8=1`이 필요했습니다.

## 변경 내용

- `graphori/agents/openai.yaml`을 BOM 없는 UTF-8과 LF로 다시 저장했습니다. `display_name`, `short_description`, `default_prompt`의 큰따옴표와 `default_prompt`의 `$graphori`는 유지했습니다.
- `graphori/scripts/validate_skill.py`를 추가했습니다. 외부 PyYAML이나 Orca 없이 UTF-8/LF, SKILL frontmatter의 `name`과 `description`, YAML 필수 키·큰따옴표·`$graphori`를 검사합니다.
- `graphori/assets/.gitkeep`를 추가했습니다.
- README와 `docs/PROCESS.md`에 수정 후 재검수 대기, macOS `deferred/unknown`, 실행 명령을 적었습니다.
- 다음 단계인 `core`, `runtime`, `dashboard`는 구현하지 않았습니다.

## 실행 명령과 실제 결과

Windows PowerShell에서 실행했습니다.

```powershell
python graphori/scripts/validate_skill.py graphori
```

결과: `Skill is valid!` (종료 코드 0)

```powershell
$env:PYTHONUTF8 = "1"; python <skill-creator>/scripts/quick_validate.py graphori
```

결과: `Skill is valid!` (종료 코드 0)

추가로 SKILL, YAML, canonical reference, README, PROCESS 5개 파일을 Python UTF-8 strict decode와 LF 검사로 확인했습니다.

결과: `UTF8/LF checks passed for 5 files`

macOS는 이 실행에서 확인하지 못했으므로 상태를 `deferred/unknown`으로 남깁니다.
