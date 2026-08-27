# F01 junction 우회 수정 — 검증 2팀(Claude Code) 재감사

확인 날짜: 2026-08-09 (Windows, Asia/Seoul)

작성자: 검증 2팀(Claude Code)

## 이 문서는 무엇인가

지난번에 검증 2팀이 `ast`, `blobs/sha256` 폴더 자리에 junction(윈도우
폴더 바로가기)을 놓아서 프로젝트 밖에 파일을 만들 수 있다는 구멍을
찾았다(`F01_BOUNDARY_TEAM2_AUDIT.md`). 구현팀이 그 구멍을 고쳤다고
`F01_JUNCTION_FIX_REPORT.md`에 썼다. 이 문서는 그 수정이 진짜로 막는지
검증 2팀이 다시 확인한 기록이다.

이번에도 구현 코드나 기존 문서는 한 글자도 고치지 않았다. 이 새 문서만
썼다. 두 보고서(`F01_BOUNDARY_TEAM2_AUDIT.md`, `F01_JUNCTION_FIX_REPORT.md`)
는 먼저 읽었지만 내용을 그대로 믿지 않고 코드를 직접 읽고, 같은 공격을
완전히 새로운 외부 폴더에서 내 손으로 다시 해봤다.

## 결론

**Windows current gate: PASS**

이유는 이렇다.

- `ast`, `blobs/sha256` 두 공격을 예전과 똑같은 방법으로, 하지만 예전에
  쓴 폴더와는 다른 완전히 새 폴더에서 다시 시도했다. 두 공격 모두
  파일을 하나도 만들지 못하고 `IllegalArgumentException`으로 실패했다.
- 외부 표시 파일(`marker.txt`)의 SHA256과 폴더 안 파일 목록은 공격 시도
  전후로 완전히 똑같았다.
- 코드를 읽어보니 `analyze`가 시작될 때 `PathBoundary.validate`가
  `ast`, `ast/raw.json`, `blobs`, `blobs/sha256`, `events`를 포함한 모든
  경로를 먼저 검사하고, 그다음에야 Clang을 실행한다. 즉 "파일을 만들기도
  전에 멈춘다"는 약속이 이 두 폴더에도 적용됐다.
- 전체 단위 테스트(15개)를 `--rerun-tasks`로 다시 돌렸고 전부 통과했다.
  그 안에는 이번에 고친 것과 정확히 같은 상황(외부 `ast` junction, 외부
  `blobs/sha256` junction)을 확인하는 자동 테스트 2개가 새로 들어있었다.
- 구현팀이 이미 새 폴더(`build/f01-junction-fix`)에서 F01 다섯 단계를
  전부 실행해둔 결과가 남아있어서, 그 폴더의 핵심 숫자(이벤트 수, query
  결과, AST golden 검사, AAR/ELF SHA, replay 결과, windows-gate-report.json)
  와 AST 원본의 경로 누출 여부를 직접 읽어서 대조했다. 전부 보고서에 적힌
  값과 똑같았고, AST 원본 안에 이 컴퓨터의 사용자 경로(`C:\Users`,
  `C:/Users`, 계정 이름)는 0건이었다. 그래서 F01 전체를 또 새로 실행하지
  않았다(아래 6번에 이유를 적었다).

macOS는 이번에도 이 컴퓨터에서 실행하지 않았다. 계속 `deferred/unknown`이며,
F01 전체가 끝났다는 뜻이 아니다.

## 1. 코드 리뷰 — `PathBoundary`와 파일을 쓰는 모든 곳

다음 파일을 전부 읽었다: `PathBoundary.kt`, `Analyzer.kt`, `Artifacts.kt`,
`Toolchain.kt`, `Ledger.kt`, `Main.kt`, `AstPathNormalizer.kt`.

### 1-1. `PathBoundary`에 생긴 새 함수 세 개

`PathBoundary.kt`를 열어보면 이제 이런 함수가 있다.

```kotlin
fun createDirectories(project: Path, label: String, path: Path) {
    validate(project, mapOf(label to path))
    Files.createDirectories(path)
}

fun write(project: Path, label: String, path: Path, bytes: ByteArray) {
    val parent = path.toAbsolutePath().normalize().parent ?: error("$label has no parent")
    createDirectories(project, "$label-parent", parent)
    validate(project, mapOf(label to path))
    Files.write(path, bytes)
}

fun writeString(project: Path, label: String, path: Path, content: String) {
    val parent = path.toAbsolutePath().normalize().parent ?: error("$label has no parent")
    createDirectories(project, "$label-parent", parent)
    validate(project, mapOf(label to path))
    Files.writeString(path, content)
}
```

폴더를 만들기 직전(`Files.createDirectories`), 파일을 쓰기 직전
(`Files.write`, `Files.writeString`)마다 `validate(...)`를 먼저 부른다.
`validate`는 예전과 같은 방식으로 `nearestExistingAncestor(...).toRealPath()`
를 확인해서, junction을 따라간 "진짜 위치"가 프로젝트 안인지 본다.

### 1-2. `Files.write`/`writeString`/`createDirectories`를 직접 부르는 곳이
있는지 전부 찾아봄

```text
grep -rn "Files\.(write|writeString|createDirectories|newOutputStream|newBufferedWriter|copy)|FileOutputStream|FileWriter" doctori-analyzer/src/main/kotlin
```

결과: `PathBoundary.kt` 안의 세 줄(29쪽 `createDirectories`, 39쪽
`write`, 47쪽 `writeString`) **뿐**이었다. `Analyzer.kt`, `Artifacts.kt`,
`Toolchain.kt`, `Ledger.kt`, `Main.kt` 어디에도 `Files.write`나
`Files.createDirectories`를 직접 부르는 곳이 없었다. 즉 파일이나 폴더를
만드는 길은 `PathBoundary`의 세 함수 하나로 전부 모여 있고, 그 세 함수는
전부 쓰기 직전에 검사한다. 예전처럼 "검사 목록에서 빠진 폴더"가 생길
방법이 코드 구조상 훨씬 줄었다.

### 1-3. `analyze`가 제일 먼저 하는 일 — 자기가 만들 모든 경로를 미리 검사

`Analyzer.kt`의 `analyze(...)` 함수를 보면 이렇다.

```kotlin
fun analyze(root: Path, runDir: Path, variant: String, abi: String): F01Context {
    PathBoundary.validate(root, mapOf("run-dir" to runDir))
    validateAnalyzeOutputs(root, runDir)   // <- Clang을 실행하기 전에 호출
    ...
    val astProcess = ProcessRunner.run(toolchain.clangxx, ...)   // Clang은 이 뒤에 실행됨
```

그리고 `validateAnalyzeOutputs`는 이렇다.

```kotlin
internal fun validateAnalyzeOutputs(root: Path, runDir: Path) {
    val paths = linkedMapOf(
        "run-dir" to runDir,
        "ast" to runDir.resolve("ast"),
        "ast/raw.json" to runDir.resolve("ast/raw.json"),
        "ast/stderr.txt" to runDir.resolve("ast/stderr.txt"),
        "ast/normalized.json" to runDir.resolve("ast/normalized.json"),
        "blobs" to runDir.resolve("blobs"),
        "blobs/sha256" to runDir.resolve("blobs/sha256"),
        "events" to runDir.resolve("events"),
        "events/events-01.jsonl" to runDir.resolve("events/events-01.jsonl"),
        "input-manifest.json" to runDir.resolve("input-manifest.json"),
        "context.json" to runDir.resolve("context.json"),
        "build-manifest.json" to runDir.resolve("build-manifest.json"),
        "toolchain.json" to runDir.resolve("toolchain.json"),
        "target-syntax.cpp" to runDir.resolve("target-syntax.cpp")
    )
    PathBoundary.validate(root, paths)
}
```

지난번 감사에서 검사 목록에 없었던 `ast`, `blobs`, `blobs/sha256`가 이제
전부 들어있다. 이 검사는 `ProcessRunner.run(toolchain.clangxx, ...)`
(Clang 실행, 87번째 줄)보다 앞(78번째 줄)에서 실행되므로, "AST를 뽑기도
전에 junction을 잡아낸다"는 순서가 코드로 확인된다.

또 `ArtifactInspector.inspect(...)`(`Artifacts.kt`, `blobs/sha256`에
ELF 바이트를 쓰는 곳)는 `Analyzer.kt`의 82번째 줄, 즉 `validateAnalyzeOutputs`
호출(78번째 줄) **뒤**에 호출된다. 그래서 `blobs/sha256` junction이 있으면
`ArtifactInspector.inspect`가 실행되기도 전에 이미 멈춘다. 이건 아래
3번에서 실제로도 확인했다.

## 2. 전체 단위 테스트 — `--rerun-tasks`

```text
./gradlew.bat test --rerun-tasks --no-daemon --console=plain
```

결과: **`BUILD SUCCESSFUL in 41s`** (4 actionable tasks: 4 executed,
캐시를 쓰지 않고 전부 새로 실행).

테스트 결과 파일(`build/test-results/test/*.xml`)을 직접 세어보니 다음과
같았다.

| 테스트 클래스 | 테스트 수 | 실패 |
| --- | --- | --- |
| `AstPathNormalizerTest` | 1 | 0 |
| `CanonicalIdTest` | 1 | 0 |
| `CanonicalJsonTest` | 1 | 0 |
| `EventValidationTest` | 2 | 0 |
| `F01AcceptanceTest` | 4 | 0 |
| `PathBoundaryTest` | 6 | 0 |
| **합계** | **15** | **0** |

`F01_JUNCTION_FIX_REPORT.md`가 말한 "15 tests" 그대로였다.

`PathBoundaryTest.kt`를 직접 열어서 새로 추가된 두 테스트를 읽었다.

- `analyze rejects an external ast junction before writing AST output` —
  `run/ast`를 junction으로 만들고 `analyze`를 부르면
  `IllegalArgumentException`이 나고, 외부 `marker.txt`가 그대로이고,
  외부에 `raw.json`/`.so`가 생기지 않는지 확인한다.
- `analyze rejects an external blobs sha256 junction before writing ELF
  bytes` — 같은 방식으로 `blobs/sha256`를 확인한다.

두 테스트 모두 윈도우에서는 `mklink /J`로 진짜 junction을 만들고, 그
junction을 못 만들면 "성공한 척" 넘어가지 않고 실패하게 되어 있는 것도
확인했다(`createDirectoryLink` 함수, `assertEquals(0, process.waitFor(),
output)`).

## 3. 같은 공격을 완전히 새 폴더에서 내 손으로 다시 재현

지난번 감사와 구현팀 수정 테스트 모두 자기들만의 폴더를 썼다. 이번에는
그 어느 쪽과도 겹치지 않는 **새 프로젝트-안 run-dir 두 개**와 **새
프로젝트-밖 표시 폴더 두 개**를 만들어서 처음부터 다시 시도했다.

### 3-1. 준비 — 새 폴더 만들기

```text
프로젝트 밖(표시 파일 폴더, 이번에 새로 만듦):
  <temp>/doctori-team2-reaudit-outside-ast
    marker.txt = "keep-ast-marker"
    sha256 = b54d1c328a1a7ee63d0b82a01d3ce6a5e8f3e11fb06e5d9bcdeae9ab5fc8bad1
  <temp>/doctori-team2-reaudit-outside-blobs
    marker.txt = "keep-blobs-marker"
    sha256 = a2beb29c8e66a8ef7350923bb5804b99895557b832131e5347ac578b11485cbb

프로젝트 안(run-dir, 이번에 새로 만듦, 예전 감사 폴더와 이름이 다름):
  build/f01-team2-reaudit-ast
  build/f01-team2-reaudit-blobs
```

각 run-dir에 대해 `preflight`를 먼저 정상 실행해서 `toolchain.json` 등을
만들었다.

```text
gradlew.bat :doctori-analyzer:run --no-daemon --console=plain --args="f01 preflight --project . --run-dir build/f01-team2-reaudit-ast"
-> BUILD SUCCESSFUL

gradlew.bat :doctori-analyzer:run --no-daemon --console=plain --args="f01 preflight --project . --run-dir build/f01-team2-reaudit-blobs"
-> BUILD SUCCESSFUL
```

### 3-2. junction 만들기

관리자 권한 없이도 만들 수 있는 PowerShell `New-Item -ItemType Junction`
으로 만들었다(cmd `mklink /J`와 같은 결과. 이 컴퓨터 계정은 관리자 권한이
없어서 진짜 symlink는 여전히 만들 수 없다).

```powershell
New-Item -ItemType Junction -Path "build\f01-team2-reaudit-ast\ast" `
  -Target "<temp>/doctori-team2-reaudit-outside-ast"

New-Item -ItemType Junction -Path "build\f01-team2-reaudit-blobs\blobs\sha256" `
  -Target "<temp>/doctori-team2-reaudit-outside-blobs"
```

`Get-Item ... | Select-Object FullName,LinkType,Target`로 두 junction이
`LinkType=Junction`이고 원하는 바깥 폴더를 가리키는지 확인했다.

### 3-3. `analyze` 실행 — 결과: 둘 다 막힘

```text
gradlew.bat :doctori-analyzer:run --no-daemon --console=plain --args="f01 analyze --project . --run-dir build/f01-team2-reaudit-ast"

-> Task :doctori-analyzer:run FAILED
   Exception in thread "main" java.lang.IllegalArgumentException: ast resolves outside project root
       at com.doctori.f01.PathBoundary.validate(PathBoundary.kt:23)
       at com.doctori.f01.F01Analyzer.validateAnalyzeOutputs(Analyzer.kt:223)
       at com.doctori.f01.F01Analyzer.analyze(Analyzer.kt:78)
       at com.doctori.f01.MainKt.main(Main.kt:34)
   BUILD FAILED
```

```text
gradlew.bat :doctori-analyzer:run --no-daemon --console=plain --args="f01 analyze --project . --run-dir build/f01-team2-reaudit-blobs"

-> Task :doctori-analyzer:run FAILED
   Exception in thread "main" java.lang.IllegalArgumentException: blobs/sha256 resolves outside project root
       at com.doctori.f01.PathBoundary.validate(PathBoundary.kt:23)
       at com.doctori.f01.F01Analyzer.validateAnalyzeOutputs(Analyzer.kt:223)
       at com.doctori.f01.F01Analyzer.analyze(Analyzer.kt:78)
       at com.doctori.f01.MainKt.main(Main.kt:34)
   BUILD FAILED
```

두 경우 모두 예외가 발생한 곳(`validateAnalyzeOutputs`, `Analyzer.kt:223`
→ `analyze`, `Analyzer.kt:78`)이 Clang 실행(`ProcessRunner.run`,
`Analyzer.kt:87`)보다 **앞**이다. 즉 "파일을 만들기도 전에 멈춘다"는
약속이 코드 스택트레이스로도 확인됐다.

### 3-4. 외부 표시 파일 — 공격 전후 완전히 동일

```text
공격 전:
  outside-ast/marker.txt sha256 = b54d1c328a1a7ee63d0b82a01d3ce6a5e8f3e11fb06e5d9bcdeae9ab5fc8bad1
  outside-blobs/marker.txt sha256 = a2beb29c8e66a8ef7350923bb5804b99895557b832131e5347ac578b11485cbb

공격(analyze 실패) 후:
  outside-ast 폴더 안: marker.txt 하나뿐, sha256 동일
  outside-blobs 폴더 안: marker.txt 하나뿐, sha256 동일
```

두 바깥 폴더 모두 `analyze` 실행 전후로 `ls -la` 결과가 완전히 같았고
(파일 1개, `marker.txt`), `raw.json`이나 `.so`, ELF digest 파일 같은 것은
하나도 생기지 않았다. SHA256도 바뀌지 않았다.

### 3-5. 뒷정리

junction 링크만 지웠고(`rm -f build/f01-team2-reaudit-ast/ast`,
`rm -f build/f01-team2-reaudit-blobs/blobs/sha256`), 바깥의 진짜 폴더
(target)는 지운 뒤에도 그대로 남아 있는 것을 확인했다. 확인이 끝난
뒤에는 이번 감사에서 새로 만든 바깥 표시 폴더 두 개(`outside-ast`,
`outside-blobs`)를 완전히 삭제했다. `build/f01-team2-reaudit-ast`,
`build/f01-team2-reaudit-blobs`는 `.gitignore`의 `build/` 규칙에 걸려
git에 올라가지 않으므로 증거로 남겨뒀다.

## 4. `events` 폴더는 여전히 안전한지 참고로 재확인

지난 감사에서 `events`는 "우연히" `Main.kt`의 기본 검사 목록과 겹쳐서
안전했다고 지적했었다. 이번에 보니 `Analyzer.kt`의
`validateAnalyzeOutputs`가 `events`와 `events/events-01.jsonl`도
명시적으로 목록에 넣어서 검사하고 있었다(`Analyzer.kt:215-216`). 즉
이제는 "우연"이 아니라 `ast`, `blobs`와 똑같이 의도적으로 검사 목록에
들어가 있다.

## 5. `build/f01-junction-fix` 핵심 값 대조 (구현팀이 이미 새 폴더에서 실행한 결과)

구현팀이 `F01_JUNCTION_FIX_REPORT.md`를 쓰면서 `build/f01-junction-fix`
폴더에서 F01 다섯 단계를 전부 실행해둔 결과가 남아 있었다. 그 폴더 안
파일을 직접 읽어서 보고서에 적힌 값과 하나씩 대조했다.

| 확인 항목 | 보고서에 적힌 값 | 이번에 폴더에서 직접 읽은 값 | 일치 |
| --- | --- | --- | --- |
| events 줄 수 | 23 | `wc -l events/events-01.jsonl` → 23 | 일치 |
| query path_count | 1 | `windows-gate-report.json`의 `query_path_count` → 1 | 일치 |
| AST required_fields_check | passed | `toolchain.json` → `"required_fields_check":"passed"` | 일치 |
| AST golden_check | passed | `toolchain.json` → `"golden_check":"passed"` | 일치 |
| AAR SHA-256 | `7fcfd08eef5808f114a1d558e198598a49b22d3445c579467124b51b2ef6effc` | `windows-gate-report.json`의 `evidence_digests.aar_sha256` → 동일 | 일치 |
| ELF target SHA-256 | `71107e47b38d1b028fb4d536e31c05308a1c5be94b57b23d754c1df7a1aa1807` | `windows-gate-report.json`의 `evidence_digests.target_output_sha256` → 동일 | 일치 |
| replay byte_identical / mismatch | true / 0 | `windows-gate-report.json`의 `replay.byte_identical` → true, `replay.replay_mismatch` → 0 | 일치 |
| Windows gate / status | windows-current / observed | `windows-gate-report.json`의 `gate`, `status` → 동일 | 일치 |
| macOS | deferred / unknown | `windows-gate-report.json`의 `macos.status`, `macos.confidence` → 동일 | 일치 |

이 AAR SHA는 첫 번째 감사(`F01_BOUNDARY_TEAM2_AUDIT.md`)에서 검증 2팀이
직접 AAR을 다시 빌드해서 확인했던 값과도 같다. 이번에는 native fixture가
안 바뀌었으므로(수정 보고서에 적힌 대로) AAR을 또 새로 빌드하지 않고, 이미
만들어진 파일의 SHA만 다시 계산해서 대조했다.

```text
sha256sum fixtures/F01/library/build/outputs/aar/library-release.aar
```
값이 위 표의 AAR SHA와 같았다.

### AST 원본 경로 누출 — 0건

```text
grep -c "C:\\Users\|C:/Users\|<home>\|<user>" build/f01-junction-fix/ast/raw.json
-> 0
```

`raw.json`(3,498,074바이트, 원본 Clang AST)을 열어 이 컴퓨터의 실제 사용자
계정 이름과 `C:\Users`, `C:/Users` 형태를 찾아봤지만 한 건도 없었다.
지난 감사 이전에는 이 값이 15,533건이었던 문제였는데, 이번에도 계속 0건
이었다.

## 6. 왜 F01 전체를 또 새로 실행하지 않았는지

작업 지시에는 "새 전체 F01 실행은 구현팀이 이미 새 폴더에서 했으므로,
code/test/artifact 증거가 충분하면 반복하지 않아도 된다"고 되어 있다.
이번 감사에서 다음 세 가지가 전부 갖춰졌다고 판단했다.

1. **코드**: `PathBoundary`의 새 함수 구조와 `validateAnalyzeOutputs`가
   `ast`, `blobs/sha256`를 Clang 실행보다 먼저 검사하는 것을 직접 읽어서
   확인했다(1번).
2. **테스트**: 전체 단위 테스트 15개를 `--rerun-tasks`로 다시 돌려서
   전부 통과했고, 이번 수정과 정확히 같은 상황을 확인하는 자동 테스트
   2개가 포함되어 있었다(2번).
3. **아티팩트**: `build/f01-junction-fix` 폴더의 핵심 숫자(이벤트 수,
   query, AST golden, AAR/ELF SHA, replay, windows-gate-report.json)와
   AST 원본의 경로 누출 0건을 전부 직접 읽어서 보고서 값과 대조했다(5번).

또한 이번 감사에서 진짜로 의심스러웠던 부분, 즉 "junction 공격이 정말
막히는가"는 **완전히 새 폴더에서 직접 재현**해서 확인했다(3번). 그래서
F01 다섯 단계 전체(특히 시간이 오래 걸리는 AAR 빌드 등)를 또 새 폴더에서
반복하지 않았다.

## 7. 최종 판단

**판정: PASS**

- 지난 감사에서 찾은 `ast`, `blobs/sha256` junction 우회 두 가지 모두,
  같은 방법을 완전히 새 독립 외부 폴더에서 다시 시도했을 때 파일을
  하나도 만들지 못하고 실패했다. 외부 표시 파일의 SHA256과 폴더 안 파일
  목록은 공격 시도 전후로 완전히 동일했다.
- 코드를 읽어보니 이 두 폴더가 이제 `analyze`가 Clang을 실행하기 전에
  검사하는 목록에 명시적으로 들어있고, 파일을 쓰는 모든 경로가
  `PathBoundary`의 세 함수(`createDirectories`, `write`, `writeString`)
  하나로 모여서 그때마다 검사를 거친다.
- 전체 단위 테스트(15개)가 `--rerun-tasks`로 전부 통과했고, 이번 수정을
  검증하는 자동 테스트 2개가 새로 포함되어 있었다.
- `build/f01-junction-fix` 폴더의 핵심 숫자와 AST 원본의 경로 누출 0건을
  직접 읽어서 대조했고, 전부 기존 보고서와 일치했다.
- 새로운 우회는 찾지 못했다.

macOS는 여전히 `deferred/unknown`이다. 이 문서는 Windows current gate만
다룬다.
