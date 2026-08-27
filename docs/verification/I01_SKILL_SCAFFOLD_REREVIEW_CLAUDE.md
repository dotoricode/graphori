# I01 스킬 뼈대 재검수: LUNA 수정 결과 확인

검수일: 2026-08-09 (Asia/Seoul)
검수자: Claude (독립 재검수 세션 — I01 원 작성자·수정자와 분리)
검수 방법: 정적 파일 대조 + 실제 바이트 확인(hexdump) + 명령 재실행(exit code 확인). **구현·수정하지 않았다. 코드와 문서를 한 줄도 고치지 않았다.**

입력 문서:

- `docs/verification/I01_SKILL_SCAFFOLD_REVIEW_CLAUDE.md` (이전 검수, 판정 REVISE, 사유 3가지)
- `docs/verification/I01_FIX_REPORT_LUNA.md` (LUNA의 수정 보고서)

---

## 0. 최종 판정

> **APPROVE**

이전 REVISE 사유 세 가지 — (1) `agents/openai.yaml` CP949 인코딩, (2) `quick_validate.py`가 한국어 Windows 기본 코드페이지에서 크래시하고 이 사실이 안내되지 않음, (3) 빈 `assets/`·`scripts/` 디렉터리에 placeholder 없음 — 를 모두 실제 파일과 명령 재실행으로 독립 확인했다. 세 가지 모두 실제로 고쳐졌고, LUNA의 보고서 내용이 파일 상태와 일치한다. 차단급 결함을 찾지 못했다.

---

## 1. `agents/openai.yaml` 인코딩·내용 확인 — **PASS**

**확인 방법**: 바이트 직접 검사(Python `read_bytes()` + strict UTF-8 디코딩, `xxd` hexdump), `file` 명령.

```
$ python3 -c "
data = open('graphori/agents/openai.yaml','rb').read()
print('has BOM:', data.startswith(b'\xef\xbb\xbf'))
print('has CR:', b'\r' in data)
text = data.decode('utf-8', errors='strict')
print('utf-8 strict decode OK, len', len(text))
"
has BOM: False
has CR: False
utf-8 strict decode OK, len 150

$ file graphori/agents/openai.yaml
graphori/agents/openai.yaml: Unicode text, UTF-8 text
```

hexdump로 줄바꿈이 전부 `0a`(LF)뿐이고 `0d`(CR)가 전혀 없음을 확인했고, 한글 구간(`ec9c84 ed9798 ...`)이 CP949 2바이트 패턴(`c0a7 c7e8 ...`, 이전 검수 3장 참조)이 아니라 정상적인 UTF-8 3바이트 시퀀스(0xEC–0xED 계열, 한글 U+AC00–U+D7A3 범위)임을 확인했다. **strict UTF-8, BOM 없음, CR 없음(LF만)** — 이전 REVISE 사유(1)이 실제로 해소되었다.

파일 내용도 직접 읽어 대조했다:

```yaml
interface:
  display_name: "Graphori"
  short_description: "위험 기반 DAG로 에이전트 작업을 라우팅하는 스킬"
  default_prompt: "$graphori로 이 작업을 위험도에 맞는 DAG로 라우팅해 주세요."
```

- 필수 3키(`display_name`, `short_description`, `default_prompt`) 모두 존재하고 값이 채워져 있음 — **PASS**
- 세 값 모두 큰따옴표로 감싸져 있음(의미 있는 문자열 quoting, 장식이 아님) — **PASS**
- `default_prompt`가 `$graphori`를 그대로 포함함 — **PASS**
- 이전 검수와 문자열 내용이 동일함(재저장만 되고 의미 변경 없음) — **PASS**

---

## 2. `graphori/scripts/validate_skill.py` — Windows 기본 cp949 실행 및 정적 검토 — **PASS**

**(A) 기본 코드페이지(=PYTHONUTF8 미설정) 실행**

이 머신의 `locale.getpreferredencoding()`은 여전히 `cp949`임을 재확인했다(콘솔 코드페이지가 65001이어도 Python의 텍스트 모드 기본 인코딩은 별개로 cp949를 반환한다 — 이전 검수 5장과 동일한 근본 원인).

```
$ python -c "import locale; print(locale.getpreferredencoding())"
cp949

$ Remove-Item Env:PYTHONUTF8 -ErrorAction SilentlyContinue
$ python graphori\scripts\validate_skill.py graphori
Skill is valid!
EXIT_CODE=0
```

cmd.exe에서 `PYTHONUTF8`을 명시적으로 비운 채로도 재확인했다:

```
$ cmd /c "set PYTHONUTF8=&& python graphori\scripts\validate_skill.py graphori & echo EXIT_CODE=%ERRORLEVEL%"
Skill is valid!
EXIT_CODE=0
```

두 경우 모두 **exit code 0**. 이전 검수에서 재현했던 `quick_validate.py`의 cp949 크래시(`UnicodeDecodeError: 'cp949' codec can't decode byte 0xeb ...`)가 `validate_skill.py`에서는 발생하지 않는다.

**(B) 정적 검토 — 표준 라이브러리만 사용, Orca/PyYAML/절대 사용자 경로 미의존**

소스(`graphori/scripts/validate_skill.py`)를 전문 대조했다.

- import 목록: `from __future__ import annotations`, `re`, `sys`, `from pathlib import Path` — 4개뿐. PyYAML(`import yaml`) 없음, Orca 관련 모듈 없음, 외부 패키지 없음. **PASS**
- 파일 읽기 방식이 크래시 원인을 정면으로 회피한다: `read_utf8()`(19행 근처)가 `path.read_bytes()`로 바이트를 먼저 읽고, BOM·CR을 바이트 레벨에서 검사한 뒤 `data.decode("utf-8")`을 **명시적으로** 호출한다. 이전 검수가 지목한 크래시 원인(`Path.read_text()`가 인코딩 미지정 시 `locale.getpreferredencoding()`을 묵시적으로 사용해 cp949로 디코딩을 시도함)을 애초에 만들지 않는 구조다. **PASS**
- 기본 실행 대상 경로: `root = Path(argv[1]) if len(argv) == 2 else Path(__file__).resolve().parents[1]` — 스크립트 자신의 위치를 기준으로 한 **상대 경로**이며, `<home>\...` 같은 하드코딩된 절대 사용자 경로가 코드 어디에도 없다. **PASS**
- 검사 범위: SKILL.md frontmatter(`name`/`description` 존재, `name == "graphori"`), `agents/openai.yaml`의 UTF-8/CRLF/트레일링 공백/quote/필수 3키/`$graphori` 포함 여부를 모두 stdlib 정규식·문자열 처리만으로 검사한다. PyYAML 없이 "문서화된 작은 YAML 서브셋만" 검사한다는 LUNA 보고서의 설명과 일치한다.

---

## 3. 공식 skill-creator `quick_validate.py` (지정 경로) — PYTHONUTF8=1 — **PASS**

지시받은 경로만 사용했다(루트 검색 없이):

```
<home>\AppData\Roaming\orca\codex-runtime-home\home\skills\.system\skill-creator\scripts\quick_validate.py
```

```
$ Test-Path "<home>\AppData\Roaming\orca\codex-runtime-home\home\skills\.system\skill-creator\scripts\quick_validate.py"
True

$ $env:PYTHONUTF8 = "1"
$ python "<home>\AppData\Roaming\orca\codex-runtime-home\home\skills\.system\skill-creator\scripts\quick_validate.py" graphori
Skill is valid!
EXIT_CODE=0
```

**exit code 0, "Skill is valid!"** 확인. 이전 REVISE 사유(2)가 해소되었음을 지정 경로에서 직접 재현했다.

참고(부가 확인, 판정에 영향 없음): README/PROCESS 문서가 실제로 안내 명령에 쓰는 경로는 이와 다른 `<home>\.claude\plugins\marketplaces\claude-plugins-official\plugins\skill-creator\...\quick_validate.py`다. 두 파일을 `diff`/`sha256sum`으로 비교한 결과 서로 다른 두 개의 실제 파일이며(SHA-256 상이, `compatibility` 필드 처리 등 세부 검증 로직도 상이), README가 가리키는 경로도 별도로 `PYTHONUTF8=1`로 실행해 **exit code 0, "Skill is valid!"**를 확인했다. 즉 README에 적힌 명령 자체는 그대로 실행해도 거짓이 아니다. 다만 이 세션에서 지정받은 "공식" 경로(AppData\Roaming\orca\...)와 README가 안내하는 경로(.claude\plugins\...)가 서로 다른 설치본이라는 점은 문서 정확성 관점의 사소한 노트로 남긴다(아래 6장 권고 참조). 이 항목의 PASS/FAIL 판정에는 영향을 주지 않는다 — 지시받은 항목(3)은 지정 경로 기준으로 이미 충족되었다.

---

## 4. `graphori/assets/.gitkeep` 및 scripts validator 추적 후보 확인 — **PASS**

```
$ find graphori -type f | sort
graphori/agents/openai.yaml
graphori/assets/.gitkeep
graphori/references/canonical-routing.md
graphori/scripts/validate_skill.py
graphori/SKILL.md

$ git log --oneline -5
fatal: your current branch 'main' does not have any commits yet

$ git status
On branch main
No commits yet
Untracked files:
  ...
	graphori/

$ git check-ignore -v graphori/assets/.gitkeep graphori/scripts/validate_skill.py
(출력 없음, exit 1 — 두 파일 모두 gitignore 대상 아님)
```

- `graphori/assets/.gitkeep`이 실제로 존재하며, 저장소가 아직 커밋 전(unstaged)이지만 `.gitignore`에 걸리지 않아 다음 `git add`/커밋 시 `assets/` 디렉터리가 살아남을 것으로 확인된다. **PASS**
- `graphori/scripts/`는 더 이상 빈 디렉터리가 아니라 실제 검사기 파일(`validate_skill.py`)을 담고 있어 placeholder가 별도로 필요 없고, 이 파일도 gitignore 대상이 아니므로 커밋 후보로 정상 추적된다. **PASS**

---

## 5. README / PROCESS 상태 표기 사실 일치 — **PASS**

`README.md`, `docs/PROCESS.md`를 실제 저장소 상태와 대조했다.

| 표기 | 문서 내용 | 실제 확인 | 판정 |
|---|---|---|---|
| Windows 검수 | "완료" | 본 재검수에서 `validate_skill.py`(exit 0), 지정 경로 `quick_validate.py`(PYTHONUTF8=1, exit 0) 둘 다 실행해 확인됨 | PASS |
| macOS 검수 | `deferred/unknown` | 이 세션은 Windows 세션이며 macOS를 직접 실행한 근거가 어디에도 없음. 문서도 "아직 확인하지 못함"이라고만 쓰고 통과했다는 주장을 하지 않음 | PASS |
| `core`/`runtime`/`dashboard` | "아직 구현하지 않았습니다" | `find . -iname "core" -o -iname "runtime" -o -iname "dashboard"` 결과 해당 이름의 디렉터리/파일이 저장소 어디에도 없음 | PASS |

README가 문서화한 두 검증 명령(`validate_skill.py`, `PYTHONUTF8=1` + 지정 `quick_validate.py`)을 그대로 실행해 모두 exit 0을 재현했으므로, "검수 명령" 절의 안내도 실제로 작동한다. **PASS**

---

## 6. 쓰기 안전성 — **PASS**

이번 재검수 세션에서는 읽기(Read)와 실행(Bash/PowerShell 명령 실행)만 수행했다. `graphori/`, `README.md`, `docs/PROCESS.md` 등 UTF-8 원본 파일에 대한 쓰기(Edit/Write)는 전혀 수행하지 않았다. 이 재검수 보고서(`docs/verification/I01_SKILL_SCAFFOLD_REREVIEW_CLAUDE.md`) 자체만 새로 작성했다.

---

## 7. 결론

이전 REVISE 사유 세 가지가 모두 실제로 해소되었음을 독립적으로 재현·확인했다.

1. `agents/openai.yaml` — CP949 → strict UTF-8/BOM 없음/LF만. 필수 3키·큰따옴표·`$graphori` 내용 유지. **PASS**
2. `graphori/scripts/validate_skill.py` — 한국어 Windows 기본 코드페이지(cp949)에서 exit code 0. stdlib(`re`/`sys`/`pathlib`)만 사용, PyYAML·Orca·하드코딩된 절대 사용자 경로 없음. **PASS**
3. 지정된 공식 `quick_validate.py`(`...\AppData\Roaming\orca\codex-runtime-home\home\skills\.system\skill-creator\scripts\quick_validate.py`) — `PYTHONUTF8=1`로 exit code 0, "Skill is valid!". **PASS**
4. `graphori/assets/.gitkeep` 존재, `graphori/scripts/validate_skill.py`와 함께 gitignore 미적용 상태로 커밋 추적 후보임을 확인. **PASS**
5. README/PROCESS의 Windows 확인·macOS `deferred/unknown`·core/runtime/dashboard 미구현 표기가 실제 저장소 상태 및 명령 재실행 결과와 일치. **PASS**
6. 이번 재검수는 UTF-8 원본 파일을 전혀 수정하지 않았다. **PASS**

**최종 판정: APPROVE**

권고(수정은 이번 재검수 범위 밖, 강제 사유 아님):
- README/PROCESS가 안내하는 `quick_validate.py` 경로(`.claude\plugins\marketplaces\...`)와 이 세션에서 "공식"으로 지정된 경로(`AppData\Roaming\orca\codex-runtime-home\...`)가 서로 다른 설치본(SHA-256 상이, 검증 로직 일부 상이)이다. 두 경로 모두 현재는 통과하지만, 두 스킬-크리에이터 설치본이 존재한다는 사실과 어느 쪽이 이 프로젝트의 canonical인지 한 줄 명시해 두면 이후 혼선을 줄일 수 있다.
