# Graphori 대시보드 스킬

이 스킬은 가장 최근 Graphori 작업 화면을 찾아 브라우저로 열어 준다. 작업을 새로
시작하거나 파일을 수정하지 않고, 이미 기록된 진행 상황만 보여 준다.
자세한 동작 규칙은 [`SKILL.md`](SKILL.md)에 있다.

## 설치

macOS와 Linux:

```bash
./scripts/install_skill.sh --target both --skill graphori-dashboard
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_skill.ps1 `
  -Target both -Skill graphori-dashboard
```

## 사용

- Codex: `$graphori-dashboard`
- Claude Code: `/graphori-dashboard`

화면이 열리지 않으면 먼저 `graphori dashboard --no-open`을 실행해 표시되는 주소를
직접 브라우저에 입력한다.
