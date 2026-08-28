# I10 installable skill build

## 범위

PR #2는 canonical Graphori skill, Codex/Claude 설치기, Markdown 디렉터리 색인, truthful dashboard snapshot publisher를 추가했다. skill 폴더에는 skill-creator 규칙에 따라 README를 만들지 않았다.

## 설치 경로 계약

| 대상 | 정확한 경로 |
|---|---|
| Codex (기본) | `<home>/.agents/skills/graphori` |
| Codex (특수 환경 override) | `<GRAPHORI_CODEX_SKILLS_DIR>/graphori` |
| Claude Code | `<home>/.claude/skills/graphori` |

설치기는 canonical `graphori/`만 복사한다. 다른 skill은 건드리지 않는다. 대상이 있고 내용이 다르면 기본적으로 중단하며, `--force`/`-Force`일 때만 날짜가 붙은 백업을 만들고 교체한다. 복사 후 `graphori/scripts/validate_skill.py`를 실행한다.

## 실행 명령

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_skill.ps1 -Target both -Force
```

```sh
./scripts/install_skill.sh --target both --force
```

최종 dashboard를 새 main 상태에서 열 때 사용할 명령과 run id:

```powershell
$root = (Get-Location).Path
$runId = "pr2-final-<sha>"
python -m src.graphori_core.cli --root $root --run-id $runId run -- python -m unittest discover -s tests
python scripts/dashboard_server.py --root $root --port 8765
```

이 명령은 별도 최종 탭에서 `http://127.0.0.1:8765/?run=$runId`를 열 때 사용한다. 기존 Orca 탭/서버는 닫지 않는다.

## 현재 검증 결과

- 브랜치: `feat/installable-skills-and-doc-indexes`
- 기준 commit: `origin/main`의 `7ec8d21` (PR #1 merge 결과)
- 문서 색인: 74개 Markdown을 모두 색인, skill 폴더와 README 자기 자신만 예외
- 기존 회귀: 118개 테스트 통과
- 통과: skill validator, compileall, dashboard finite smoke, `git diff --check`
- Windows temp-home: PowerShell installer 통과
- 실제 설치: Codex와 Claude Code 각각 위 경로에 canonical 파일 4개 설치, 두 경로 validator 통과
- POSIX shell temp-home: Windows의 Git Bash가 `HOME`을 profile로 다시 쓰므로 로컬에서는 `deferred`; macOS hosted runner에서 실행하도록 CI에 넣음
- macOS 직접 실행: `deferred`; hosted CI fixture 결과만 성공으로 기록
- hosted Actions: run `31327819856`와 `31327821989`에서 Windows 3.11, Windows 3.12, macOS 모두 success
- PR #2: `https://github.com/dotoricode/graphori/pull/2`, Ready for review

최종 dashboard를 새 main 상태에서 열 때 사용할 정확한 명령은 다음과 같다. `<sha>`는 최종 commit SHA로 바꾼다.

```powershell
$root = (Get-Location).Path
$runId = "pr2-final-<sha>"
python -m src.graphori_core.cli --root $root --run-id $runId run -- python -m unittest discover -s tests
python scripts/publish_snapshot.py --root $root --run-id $runId --output "$root/build/$runId.snapshot.json"
python scripts/dashboard_server.py --root $root --port 8765
```

macOS/Linux에서 확인할 때는 현재 폴더의 물리적 절대 경로를 저장하고, 경로를 꼭 따옴표로 감쌉니다.

```sh
repo_root="$(pwd -P)"
run_id="pr2-final-<sha>"
python3 -m src.graphori_core.cli --root "$repo_root" --run-id "$run_id" run -- python3 -m unittest discover -s tests
python3 scripts/publish_snapshot.py --root "$repo_root" --run-id "$run_id" --output "$repo_root/build/$run_id.snapshot.json"
python3 scripts/dashboard_server.py --root "$repo_root" --port 8765
```

`http://127.0.0.1:8765/`를 새 최종 탭에서 열고, 기존 Orca 탭과 서버는 닫지 않는다. snapshot의 100%는 verifier verdict와 terminal node가 실제 journal에 있을 때만 표시된다.
