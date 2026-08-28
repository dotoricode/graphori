# I01 스킬 뼈대 검수: graphori/SKILL.md, agents/openai.yaml, references/canonical-routing.md, README

검수일: 2026-08-09 (Asia/Seoul)
검수자: Claude (독립 검수 세션 — I01 결과물 작성자와 분리)
검수 방법: 정적 파일 대조 + 실제 인코딩 바이트 확인(hexdump/코드페이지 디코딩) + `quick_validate.py` 실행 재현(S, E1). **구현·수정하지 않았다. 코드와 문서를 한 줄도 고치지 않았다.**

검수 대상:

- `graphori/SKILL.md`
- `graphori/agents/openai.yaml`
- `graphori/references/canonical-routing.md`
- `graphori/assets/`, `graphori/scripts/` (빈 디렉터리)
- `README.md` (repo root)
- `<home>\.claude\plugins\marketplaces\claude-plugins-official\plugins\skill-creator\skills\skill-creator\scripts\quick_validate.py` (Windows 기본 코드페이지 vs `PYTHONUTF8=1` 재현)

---

## 0. 최종 판정

> **REVISE**

frontmatter 최소화, 인용부호, `$graphori` 트리거, MCP 미요구, canonical 문서 미복제, README 상태 표기는 모두 정확했다. 그러나 차단급 결함 두 가지를 확인했다:

1. **`graphori/agents/openai.yaml` 파일 자체가 UTF-8이 아니라 CP949(EUC-KR)로 저장되어 있다.** UTF-8을 기대하는 표준 방식으로 열면(예: macOS/Linux 기본, 대부분의 YAML 파서·git diff 도구) `UnicodeDecodeError`로 즉시 깨진다. 이 스킬의 존재 이유 중 하나가 "Windows/macOS 이식성"인데, 정작 스킬 자신의 파일이 이식되지 않는다.
2. **`quick_validate.py`를 한국어 Windows 기본 코드페이지(cp949, 활성 코드 페이지 949)에서 그대로 실행하면 크래시한다.** `PYTHONUTF8=1`을 주면 통과한다. 지시받은 판정 규칙대로 "기본 코드페이지 실패가 사용자 경험을 깨면 REVISE"에 해당한다.

부가로 빈 `assets/`, `scripts/` 디렉터리가 `.gitkeep` 없이 존재해, 첫 커밋 이후 clone하는 사용자에게는 사라질 것으로 예상되는 점도 REVISE 사유에 포함한다.

---

## 1. 12살도 이해하는 요약

이 폴더는 "Graphori"라는 새 기술을 쓰기 위한 설명서 세트예요. 설명서 표지(SKILL.md), 어떤 도구가 필요한지 적은 카드(openai.yaml), 어디 가면 진짜 설계도가 있는지 알려주는 안내판(canonical-routing.md), 그리고 아직 그림도 프로그램도 안 들어있는 빈 상자 두 개(assets, scripts)로 되어 있어요.

표지와 안내판은 잘 썼어요. 한국어로 되어 있고, 다른 설계도를 통째로 베끼지 않고 "필요할 때 가서 읽어라"고만 알려줘요. 저장소 설명(README)도 "아직 뼈대만 있다"고 정직하게 써 놓았고, 실제로 찾아봐도 진짜 프로그램(core, runtime, dashboard)은 어디에도 없었어요. 여기까지는 맞아요.

그런데 도구 카드(openai.yaml)를 컴퓨터 안에서 진짜 글자 코드로 열어봤더니, 한글이 "보통 방식(UTF-8)"이 아니라 "옛날 한글 윈도우 방식(CP949)"으로 저장돼 있었어요. 이건 이 스킬이 스스로 내세우는 "윈도우랑 맥에서 똑같이 되게 하자"는 약속을 스스로 어긴 거예요. 맥이나 리눅스, 또는 보통 방식만 읽는 프로그램으로 이 파일을 열면 글자가 깨지거나 아예 에러가 나요. 실제로 파이썬으로 "보통 방식(UTF-8)"으로 열어보니 바로 에러가 났어요.

그리고 검사 도구(quick_validate.py)도 한국어 윈도우의 기본 설정 그대로 실행하면 에러를 내면서 멈춰버렸어요. `PYTHONUTF8=1`이라는 특별한 스위치를 켜야만 "통과!"라고 나왔어요. 이 스위치를 켜야 한다는 말은 어디에도 적혀 있지 않았기 때문에, 이 저장소를 처음 받은 한국어 윈도우 사용자는 검사 도구부터 실패하는 걸 보게 돼요.

그래서 이번 판정은 "다시 해와요(REVISE)"예요. 문서 내용 자체는 괜찮지만, 파일을 저장한 방식(글자 코드)과 빈 상자 두 개(assets, scripts) 처리가 실제로 다른 컴퓨터·다른 운영체제에서 재현되지 않아요.

---

## 2. 방법과 한계

- SKILL.md·agents/openai.yaml·references/canonical-routing.md·README.md의 텍스트 내용을 직접 읽고 대조했다(S).
- `xxd`(hexdump)와 `System.Text.Encoding.GetEncoding(949)`(PowerShell)로 `openai.yaml`의 실제 바이트를 확인해 인코딩을 판정했다(E1, 재현 가능).
- `python -c "open(..., encoding='utf-8')"` / `encoding='cp949'`로 두 인코딩 가정을 각각 실제로 열어 성공/실패를 재현했다(E1).
- `quick_validate.py`를 (a) 아무 환경변수 없이(이 머신의 활성 코드 페이지 949, cp949) (b) `PYTHONUTF8=1`을 준 채로 각각 실행해 출력과 종료 코드를 그대로 기록했다(E1, 재현 가능. 사용한 인터프리터: `<home>\AppData\Local\Programs\Python\Python312\python.exe`, Python 3.12.1, PyYAML 설치됨).
- `git status`, `git ls-files`로 저장소가 아직 커밋이 하나도 없는 상태(unstaged)임을 확인했고, 이 사실을 바탕으로 빈 디렉터리의 향후 커밋 후 동작을 추론했다(git의 일반 동작 — 빈 디렉터리는 추적되지 않음 — 에 근거한 판단이며, 실제 커밋·clone을 재현하지는 않았다. 이 점은 한계로 남긴다).
- macOS 환경 자체는 이 세션에서 직접 재현하지 못했다(Windows 세션). "UTF-8을 기대하는 표준 오픈 방식으로 읽으면 실패한다"는 사실만 확인했고, 이는 macOS/Linux의 기본 인코딩이 UTF-8이라는 일반적으로 알려진 사실에 근거해 이식성 문제로 판단한 것이지, macOS 자체에서 실행해 확인한 것은 아니다. 이 부분은 `deferred`로 남긴다.
- SKILL.md 본문의 "12살 수준" 여부는 주관적 판단이 섞인 항목이라, 근거로 skill-creator 플러그인 자신의 작성 가이드(`skill-creator/SKILL.md` "Communicating with the user" 절)를 대조 기준으로 사용했다.

---

## 3. 항목별 확인 결과

| # | 확인 항목 | 판정 | 근거 |
|---|---|---|---|
| 1 | SKILL.md frontmatter가 `name`/`description`만 있는지 | **PASS** | `graphori/SKILL.md:1-4`. `name: graphori`, `description: ...` 두 키만 존재. `license`, `allowed-tools`, `metadata`, `compatibility` 등 다른 허용 키도, 허용되지 않는 키도 없음. |
| 2 | description의 트리거가 충분한지 | **PASS (경미한 개선 여지)** | 153자, "무엇을 하는 스킬인지"(위험 기반 DAG 라우팅) + "언제 쓰는지"(`~할 때 사용한다`) 패턴을 갖췄다. 다만 skill-creator 자신의 가이드(`skill-creator/SKILL.md:67`)는 "설명을 조금 '적극적으로'(pushy) 써서, 사용자가 명시적으로 요청하지 않아도 트리거되도록 하라"고 권장하는데, 현재 description은 단일 조건문이라 이 수준까지는 아니다. 차단 사유는 아니다. |
| 3 | 본문이 한국어인지 | **PASS** | 전체가 한국어. 영어 원문 혼입 없음. |
| 4 | 본문이 간결한지 | **PASS** | 38줄, 9단계 작업 순서 + 모드 기준 + 보고 형식 + 참고 문서. skill-creator 권장 "500줄 이하"에 크게 못 미친다. |
| 5 | 본문이 12살 수준인지 | **REVISE 수준은 아니나 미흡** | `DAG`, `canonical`, `snapshot`, `SSE`, `stale`, `heartbeat`, `fixture`, `deferred`, `unknown` 등 설명 없는 전문/영어 용어가 그대로 쓰였다(`SKILL.md:14-25`). skill-creator 자신의 작성 가이드도 "JSON, assertion 같은 용어는 사용자가 안다는 신호가 없으면 풀어서 설명하라"고 명시한다. 12살 독자 기준으로는 다수의 용어가 설명 없이 이해되기 어렵다. 이 항목 단독으로 REVISE를 걸지는 않았지만 개선이 필요하다. |
| 6 | `agents/openai.yaml`의 모든 string이 quote 되어 있는지 | **PASS** | `display_name`, `short_description`, `default_prompt` 세 값 모두 큰따옴표로 감싸져 있다. |
| 7 | `default_prompt`가 `$graphori`를 참조하는지 | **PASS** | `default_prompt: "$graphori로 이 작업을 위험도에 맞는 DAG로 라우팅해 주세요."` |
| 8 | 필수 MCP가 없는지 | **PASS** | 파일 전체가 `interface: {display_name, short_description, default_prompt}` 세 키뿐. `mcp`, `required`, `tools` 등 어떤 형태의 MCP 요구 키도 없다. |
| 9 | **`agents/openai.yaml` 파일 인코딩** | **FAIL (차단급)** | 아래 4장 참조. CP949로 저장되어 있고 UTF-8이 아니다. |
| 10 | reference routing이 canonical 문서를 복제하지 않는지 | **PASS** | `references/canonical-routing.md`는 주제→파일 경로 표와 "읽는 규칙" 4개만 담고 있다. 원문 문장을 인용·요약하지 않는다. `SKILL.md:14`도 "문서 전체를 한꺼번에 복사하거나 요약하지 않는다"고 명시해 서로 일관된다. |
| 11 | 빈 `assets/`, `scripts/` 디렉터리 처리 | **FAIL (경미~중간)** | 아래 5장 참조. `.gitkeep` 등 placeholder가 없고, 저장소는 아직 커밋이 하나도 없는 상태(`git status`: "No commits yet")다. git은 빈 디렉터리를 추적하지 않으므로, 첫 커밋 이후에는 두 디렉터리가 clone한 사용자에게 나타나지 않을 것으로 예상된다. |
| 12 | repo README의 상태 표기가 정확한지 | **PASS** | README: "현재 상태는 스킬 뼈대만 있는 단계... `core`, `runtime`, `dashboard`는 아직 구현하지 않았습니다." 저장소 전체를 검색한 결과 `core`, `runtime`, `dashboard`라는 이름의 디렉터리나 파일은 어디에도 없다. 실제 존재하는 것(SKILL.md, routing reference, UI 메타데이터, 빈 리소스 디렉터리)만 언급하고 있어 과장이 없다. |

---

## 4. `agents/openai.yaml` 인코딩 결함 — 상세 재현

```
$ file graphori/agents/openai.yaml
graphori/agents/openai.yaml: ISO-8859 text, with CRLF line terminators

$ xxd graphori/agents/openai.yaml | head -8
00000000: 696e 7465 7266 6163 653a 0d0a 2020 6469  interface:..  di
00000010: 7370 6c61 795f 6e61 6d65 3a20 2247 7261  splay_name: "Gra
00000020: 7068 6f72 6922 0d0a 2020 7368 6f72 745f  phori"..  short_
00000030: 6465 7363 7269 7074 696f 6e3a 2022 c0a7  description: "..
00000040: c7e8 20b1 e2b9 dd20 4441 47b7 ce20 bfa1  .. .... DAG.. ..
```

`c0a7 c7e8`처럼 0xA0 이상 바이트가 연속되는 패턴은 UTF-8 멀티바이트 시퀀스가 아니라 CP949(EUC-KR) 2바이트 한글 인코딩이다. PowerShell로 코드페이지 949를 강제 지정해 디코딩하면 원문이 정확히 복원된다:

```
$enc = [System.Text.Encoding]::GetEncoding(949)
$enc.GetString($bytes)
→
interface:
  display_name: "Graphori"
  short_description: "위험 기반 DAG로 에이전트 작업을 라우팅하는 스킬"
  default_prompt: "$graphori로 이 작업을 위험도에 맞는 DAG로 라우팅해 주세요."
```

반면 "표준적인" 방식, 즉 UTF-8로 열면 즉시 실패한다:

```
$ python -c "
import yaml
with open('graphori/agents/openai.yaml', encoding='utf-8') as f:
    data = yaml.safe_load(f)
"
UTF-8 read FAILED: UnicodeDecodeError 'utf-8' codec can't decode byte 0xc0 in position 62: invalid start byte
```

비교로, 저장소의 다른 텍스트 파일들은 모두 정상 UTF-8이다:

```
$ file graphori/SKILL.md graphori/references/canonical-routing.md graphori/agents/openai.yaml README.md
graphori/SKILL.md:                        Unicode text, UTF-8 text
graphori/references/canonical-routing.md: Unicode text, UTF-8 text
graphori/agents/openai.yaml:              ISO-8859 text, with CRLF line terminators
README.md:                                Unicode text, UTF-8 text
```

**영향**: macOS/Linux는 파일을 열 때 기본적으로 UTF-8을 가정하는 도구가 많고(에디터, `git diff`, 대부분의 YAML 파서 기본 옵션, 웹 기반 뷰어), 이 파일은 그 경로에서 깨지거나 예외를 던진다. 이 스킬의 SKILL.md가 스스로 "Windows/macOS 이식성을 함께 다뤄야 할 때 사용한다"고 선언하는 것과 정면으로 어긋난다. 원인은 십중팔구 이 파일이 한국어 Windows(cp949 활성 코드 페이지)에서 인코딩을 명시하지 않은 채로 저장되었기 때문으로 보인다 — 아래 5장의 `quick_validate.py` 재현 결과와 같은 근본 원인(Windows 기본 코드페이지 미고려)을 공유한다.

---

## 5. `quick_validate.py` — Windows 기본 코드페이지 vs `PYTHONUTF8=1`

스크립트 위치: `<home>\.claude\plugins\marketplaces\claude-plugins-official\plugins\skill-creator\skills\skill-creator\scripts\quick_validate.py`
대상: `graphori/` (SKILL.md만 검사하는 스크립트이며, `agents/openai.yaml`은 이 스크립트의 검사 범위가 아니다)
인터프리터: `python` → `<home>\AppData\Local\Programs\Python\Python312\python.exe`, Python 3.12.1, PyYAML 설치 확인됨
활성 코드 페이지(이 머신): `chcp` → **949**(한국어, CP949/EUC-KR 계열)

**(A) 기본 코드페이지, `PYTHONUTF8` 미설정**

```
$ cd graphori-repo-root
$ python <...>\quick_validate.py graphori
Traceback (most recent call last):
  ...
  File "...\quick_validate.py", line 22, in validate_skill
    content = skill_md.read_text()
              ^^^^^^^^^^^^^^^^^^^^
  File "...\pathlib.py", line 1028, in read_text
    return f.read()
UnicodeDecodeError: 'cp949' codec can't decode byte 0xeb in position 32: illegal multibyte sequence
EXIT CODE: 1
```

**(B) `PYTHONUTF8=1`**

```
$ PYTHONUTF8=1 python <...>\quick_validate.py graphori
Skill is valid!
EXIT CODE: 0
```

**원인**: `quick_validate.py:22`의 `skill_md.read_text()`는 인코딩을 명시하지 않는다. Python은 인코딩 미지정 시 `locale.getpreferredencoding()`을 쓰는데, 이 값은 한국어 Windows에서 `cp949`다(`locale.getpreferredencoding()` 직접 확인함). `SKILL.md` 자신은 정상 UTF-8이므로, cp949로 강제로 디코딩하다가 한글 멀티바이트 경계에서 깨져 예외가 발생한다. `PYTHONUTF8=1`은 파이썬을 UTF-8 모드로 강제해 이 문제를 우회한다.

**판정 지시 적용**: "기본 코드페이지 실패가 사용자 경험을 깨면 REVISE로 판정하라"는 지시에 따라 — 기본 코드페이지에서 크래시(예외 traceback, 종료 코드 1)가 실제로 발생했으므로 **REVISE** 사유로 반영한다. 이 결함은 `quick_validate.py`(skill-creator 플러그인 쪽 스크립트)에 있는 것이지 `graphori/SKILL.md` 자체의 결함은 아니다. 그러나 I01 산출물을 "한국어 Windows 사용자가 검증 도구로 바로 확인할 수 있는가"라는 재현성 관점에서 보면 직접적인 영향권에 있고, 4장의 `openai.yaml` 인코딩 결함과 근본 원인(Windows 기본 코드페이지 미고려)이 동일하다는 점에서 I01 검수 범위에 포함하는 것이 맞다고 판단한다.

**Windows/macOS 재현 해결책이 I01 범위에 필요한가 — 판정**: **필요하다.** 이유는 두 가지다.

1. `openai.yaml`은 I01이 직접 작성한 산출물이며, CP949 대신 UTF-8(BOM 없이)로 다시 저장하기만 하면 되는 단순한 수정으로 macOS/Linux/UTF-8 기반 도구 전체에서의 파손을 없앨 수 있다. 이건 "OS별 해결책 문서화"가 아니라 "애초에 올바른 인코딩으로 저장"이 정답이므로, 우회 문서를 추가하는 대신 파일 자체를 UTF-8로 재저장해야 한다.
2. `quick_validate.py` 쪽은 I01(graphori 스킬)의 코드가 아니라 skill-creator 플러그인의 코드이므로 이번 검수에서 직접 고칠 대상은 아니다. 다만 한국어 Windows 사용자가 이 스킬을 검증할 때 원인 모를 크래시를 만나지 않도록, **SKILL.md든 관련 검수 문서든 "Windows에서 `quick_validate.py`를 쓸 때는 `PYTHONUTF8=1`을 설정하라"는 한 줄 안내**가 어딘가에는 있어야 재현 가능하다. 현재는 그런 안내가 어디에도 없다.

---

## 6. 결론

한국어·간결성·frontmatter 최소화·`$graphori` 트리거·MCP 미요구·canonical 미복제·README 정확성은 모두 통과했다. 그러나 (1) `agents/openai.yaml`이 UTF-8이 아니라 CP949로 저장되어 이 스킬이 내세우는 이식성 목표를 스스로 어기고, 표준 UTF-8 오픈 경로에서 즉시 깨지며, (2) 검증 도구(`quick_validate.py`)가 한국어 Windows 기본 코드페이지에서 크래시하고 `PYTHONUTF8=1`을 설정해야만 통과하는데 이 사실이 어디에도 안내돼 있지 않고, (3) 빈 `assets/`·`scripts/` 디렉터리에 placeholder가 없어 첫 커밋 이후 사라질 것으로 예상되는 세 가지를 이유로 **REVISE**로 판정한다.

권고(수정은 이번 검수 범위 밖):
- `graphori/agents/openai.yaml`을 UTF-8(BOM 없음)로 재저장.
- `PYTHONUTF8=1` 필요성을 어딘가(SKILL.md 또는 별도 검증 안내)에 한 줄로 명시.
- `assets/`, `scripts/`에 `.gitkeep` 추가 또는 실제 파일이 생기기 전까지 디렉터리를 만들지 않기.
- (선택) SKILL.md description을 skill-creator 가이드대로 조금 더 "적극적인" 트리거 문구로 보강.
- (선택) 본문의 `DAG`/`canonical`/`SSE`/`stale`/`heartbeat`/`fixture` 등 용어에 짧은 설명을 덧붙여 12살 기준 이해도를 높이기.
