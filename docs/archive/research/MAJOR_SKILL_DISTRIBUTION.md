# Major Agent Skill Distribution Patterns

조사 기준일: 2026-08-27. 공개 저장소의 현재 `README`/manifest와 Codex·Claude Code 공식 문서만 확인했다. 커밋 링크는 조사 시점의 원문을 고정한다.

## 결론

주요 저장소의 기본 배포 경로는 단순 `gh repo clone` + `cp`가 아니다. 재사용 가능한 공개 기능은 각 harness의 **plugin/marketplace**로 배포하고, 여러 harness를 한 번에 지원하려는 skill-only 저장소는 **`npx skills add`** 같은 범용 설치기를 보조 경로로 둔다. 직접 복사는 로컬 개발·사내 배포·fallback에 가깝다.

Graphori도 한 저장소 안에 공통 `skills/graphori/SKILL.md`를 두되, 설치 안내는 다음처럼 분리하는 편이 현재 관행과 가장 가깝다.

- Codex: `.codex-plugin/plugin.json` + `.agents/plugins/marketplace.json`을 제공하고 Codex plugin 설치를 기본 경로로 안내한다. 직접 설치 fallback은 공식 사용자 skill 경로인 `~/.agents/skills/graphori`를 사용한다.
- Claude Code: `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json`을 제공하고 `/plugin marketplace add` → `/plugin install`을 기본 경로로 안내한다. 직접 설치 fallback은 `~/.claude/skills/graphori`를 사용한다.
- `npx skills add`는 선택적 범용 경로로 둘 수 있지만, 조사 시점 `skills` CLI의 Codex 전역 경로 표시는 Codex 공식 사용자 경로와 다르므로 그대로 유일한 설치법으로 의존하면 안 된다.

## 비교

| 저장소 | 저장소 구조 | Codex 설치 | Claude Code 설치 | 주 배포 방식 |
| --- | --- | --- | --- | --- |
| `openai/skills` | 현재 `skills/.system`, `.curated` 아래 개별 `SKILL.md` (`.experimental`은 README에만 남은 레거시 참조) | 레거시 `$skill-installer <name>` | 문서화 없음 | 내장 installer였으나 현재 deprecated |
| `openai/plugins` | `plugins/<name>/.codex-plugin/plugin.json`, `plugins/<name>/skills/`, 루트 `.agents/plugins/marketplace.json` | Codex의 Plugins UI/marketplace | 해당 없음 | Codex 네이티브 plugin marketplace |
| `anthropics/skills` | 루트 `skills/<name>/SKILL.md`; `.claude-plugin/marketplace.json`이 여러 skill을 plugin bundle로 선언 | 문서화 없음 | marketplace 등록 후 bundle 설치 | Claude 네이티브 plugin marketplace |
| `vercel-labs/agent-skills` + `vercel-labs/skills` | 루트 `skills/<name>/SKILL.md`; 별도 npm CLI가 저장소를 탐색 | `npx skills add ... -a codex` | `npx skills add ... -a claude-code` | 범용 `npx` installer |
| `obra/superpowers` | 공통 `skills/`와 `.codex-plugin`, `.claude-plugin`, `.agents/plugins/marketplace.json`을 한 저장소에 동시 제공 | 공식 Codex marketplace에서 설치 | 공식/자체 Claude marketplace에서 설치 | harness별 네이티브 marketplace |
| `wshobson/agents` | `plugins/<name>/skills/`가 원본; Claude와 Codex용 marketplace/manifest를 함께 commit | `npx codex-marketplace add ...` | `/plugin marketplace add` 후 `/plugin install` | 다중 harness marketplace + adapter |

방식별로 보면 네이티브 marketplace/plugin 명령이 4개 사례의 주 경로이고, 범용 `npx skills`가 1개 사례의 주 경로다. 조사한 저장소 중 `gh repo clone` + `cp`나 저장소 자체의 `install.sh`/`install.ps1`를 일반 사용자의 유일한 기본 경로로 삼은 곳은 없었다. 직접 복사는 OpenAI 공식 문서에서도 로컬 plugin 개발 예제로만 나타난다.

## 사례별 근거와 명령

### 1. OpenAI: `openai/skills`에서 `openai/plugins`로 이동

`openai/skills`의 현재 README는 저장소가 deprecated이며 현재 예제와 배포는 `openai/plugins` 및 plugin 빌드 가이드를 사용하라고 명시한다. 파일 안에 남은 다음 명령은 curated/experimental skill을 로컬에 넣던 **레거시 경로**다.

```text
$skill-installer gh-address-comments
$skill-installer install https://github.com/openai/skills/tree/main/skills/.experimental/create-plan
```

현재 OpenAI 저장소는 plugin 하나를 `plugins/<name>/` 아래에 두고, 필수 `.codex-plugin/plugin.json`과 선택적 `skills/`, MCP, assets 등을 묶으며 루트 `.agents/plugins/marketplace.json`이 이를 카탈로그화한다. 공식 문서도 직접 skill 폴더는 로컬 authoring에 적합하고, 다른 사람에게 재사용 가능하게 배포할 때는 plugin으로 패키징하라고 권한다. Codex가 직접 읽는 skill 경로는 repo의 `.agents/skills`와 사용자 `$HOME/.agents/skills`다.

GitHub marketplace를 통한 현재 Codex CLI 설치는 두 단계다. `<marketplace-name>`은 marketplace JSON의 최상위 `name`이며 저장소 이름이 아니다.

```bash
codex plugin marketplace add owner/repo
codex plugin add <plugin-name>@<marketplace-name>
```

Plugin에 포함된 skill은 plugin 이름으로 namespace된다. 예를 들어 plugin과 skill 이름이 모두 `graphori`면 직접 호출은 standalone의 `$graphori`가 아니라 `$graphori:graphori`다.

로컬 plugin 개발 fallback의 공식 예시는 다음처럼 복사 후 marketplace에 등록하는 방식이다. 공개 배포의 기본 명령이 아니라 테스트용이다.

```bash
mkdir -p ~/.codex/plugins
cp -R /absolute/path/to/my-plugin ~/.codex/plugins/my-plugin
```

출처: [`openai/skills` README @ `49f948f`](https://github.com/openai/skills/blob/49f948faa9258a0c61caceaf225e179651397431/README.md), [`openai/plugins` README @ `33bd952`](https://github.com/openai/plugins/blob/33bd9529725fcee78c9e51fcbaa93cd963c3a47b/README.md), [OpenAI Build skills](https://learn.chatgpt.com/docs/build-skills), [OpenAI Package your plugin](https://developers.openai.com/plugins/build/plugins), [Codex plugin add 명령 소스](https://github.com/openai/codex/blob/main/codex-rs/skills/src/assets/samples/plugin-creator/references/installing-and-updating.md), [Codex plugin skill namespace 소스](https://github.com/openai/codex/blob/main/codex-rs/ext/skills/src/loader/namespace.rs).

### 2. Anthropic: skill 묶음을 Claude plugin marketplace로 배포

`anthropics/skills`는 `skills/<name>/SKILL.md`를 원본으로 유지하면서 `.claude-plugin/marketplace.json`에서 `document-skills`, `example-skills` 같은 bundle이 포함할 skill 경로를 명시한다. README의 설치 경로는 Claude Code만 제공한다.

```text
/plugin marketplace add anthropics/skills
/plugin install document-skills@anthropic-agent-skills
/plugin install example-skills@anthropic-agent-skills
```

Claude 공식 문서가 권하는 공개 marketplace 구조도 동일하다. 저장소 루트에 `.claude-plugin/marketplace.json`, plugin 안에 `skills/<name>/SKILL.md`를 두고 사용자는 marketplace를 등록한 뒤 개별 plugin을 설치한다. 단일 사용자용 직접 skill은 `~/.claude/skills/<name>/SKILL.md`에 둘 수 있지만, 저장소 배포 예제의 기본 경로는 marketplace다.

동일한 설치를 shell에서 비대화식으로 수행할 수도 있다. 기본 scope는 user다.

```bash
claude plugin marketplace add owner/repo
claude plugin install <plugin-name>@<marketplace-name> --scope user
```

열려 있는 session이 즉시 활성화하지 못했다면 `/reload-plugins`를 실행한다. Claude plugin skill도 namespace되므로 plugin과 skill 이름이 모두 `graphori`면 `/graphori:graphori`로 호출한다. `~/.claude/skills/graphori`에 직접 둔 standalone skill만 `/graphori`다.

출처: [`anthropics/skills` README @ `3b3fad9`](https://github.com/anthropics/skills/blob/3b3fad96af16a10759d930941b4520ba0c40edae/README.md), [해당 marketplace manifest](https://github.com/anthropics/skills/blob/3b3fad96af16a10759d930941b4520ba0c40edae/.claude-plugin/marketplace.json), [Claude Code marketplace 배포](https://code.claude.com/docs/en/plugin-marketplaces), [Claude Code skills](https://code.claude.com/docs/en/slash-commands).

### 3. Vercel: 저장소는 평범한 skill tree, 설치는 범용 `npx` CLI

`vercel-labs/agent-skills`는 `skills/<name>/SKILL.md` 형태의 단순 catalog다. 별도 `vercel-labs/skills` CLI가 GitHub shorthand, 전체 URL, 특정 skill URL, 로컬 경로를 받아 지원 agent를 탐지하고 설치한다.

```bash
npx skills add vercel-labs/agent-skills
npx skills add vercel-labs/agent-skills -g -a claude-code -y
npx skills add vercel-labs/agent-skills -g -a codex -y
```

CLI는 project scope에서 Claude Code를 `.claude/skills/`, Codex를 `.agents/skills/`로 설치한다고 문서화한다. 다만 global 표는 Claude Code `~/.claude/skills/`, Codex `~/.codex/skills/`로 적혀 있어, Codex 공식 문서의 현재 사용자 경로 `$HOME/.agents/skills`와 불일치한다. 따라서 Graphori가 이 경로를 제공하더라도 Codex 직접 설치 안내는 공식 경로를 별도로 유지해야 한다.

출처: [`vercel-labs/agent-skills` README @ `dd089a8`](https://github.com/vercel-labs/agent-skills/blob/dd089a8c752c966dee8bf0f27cb625ba193ffd9e/README.md), [`vercel-labs/skills` README @ `435076e`](https://github.com/vercel-labs/skills/blob/435076e78988e1e6ec40d00b0b1d76bdbbc5419a/README.md).

### 4. Superpowers: 하나의 공통 skill tree, harness별 manifest와 설치 UX

`obra/superpowers`는 루트 `skills/`를 공유하면서 `.codex-plugin/plugin.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.agents/plugins/marketplace.json`을 함께 둔다. README는 여러 harness를 쓰면 각각 따로 설치하라고 분명히 나눈다.

Claude Code:

```text
/plugin install superpowers@claude-plugins-official
```

또는 자체 marketplace:

```text
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers-marketplace
```

Codex CLI는 `/plugins`를 열어 `superpowers`를 검색한 뒤 설치하고, Codex App은 sidebar의 Plugins에서 설치한다. 즉 같은 source tree를 쓰되 사용자 설치 절차는 하나로 합치지 않는다.

출처: [`obra/superpowers` README @ `b36e082`](https://github.com/obra/superpowers/blob/b36e0829c6d0140e93cfef2ca599b1b07d4a7797/README.md), [Codex manifest](https://github.com/obra/superpowers/blob/b36e0829c6d0140e93cfef2ca599b1b07d4a7797/.codex-plugin/plugin.json), [Claude manifest](https://github.com/obra/superpowers/blob/b36e0829c6d0140e93cfef2ca599b1b07d4a7797/.claude-plugin/plugin.json).

### 5. `wshobson/agents`: Claude 원본에서 Codex registry까지 함께 생성

이 저장소는 `plugins/`를 Claude Code용 source of truth로 두고 `.claude-plugin/marketplace.json`을 제공한다. 동시에 `.agents/plugins/marketplace.json`과 각 plugin의 `.codex-plugin/plugin.json`을 commit해 Codex가 같은 `SKILL.md`를 읽게 한다.

```text
# Claude Code
/plugin marketplace add wshobson/agents
/plugin install python-development
```

```bash
# Codex marketplace 등록; 이후 개별 plugin 설치
npx codex-marketplace add wshobson/agents
```

이는 자체 adapter/installer를 유지할 규모가 있을 때 가능한 패턴이다. Graphori처럼 plugin 수가 적은 저장소라면 변환된 skill 사본을 여러 군데 commit하기보다 공통 `skills/`와 얇은 harness별 manifest를 두는 Superpowers 방식이 더 단순하다.

출처: [`wshobson/agents` README @ `38e19c2`](https://github.com/wshobson/agents/blob/38e19c20d2b154510b0e624a2e3e186b19b5c527/README.md), [cross-harness 구조와 설치 문서](https://github.com/wshobson/agents/blob/38e19c20d2b154510b0e624a2e3e186b19b5c527/docs/harnesses.md).

## Graphori에 적용할 최소 배포안

공식 두 구조는 manifest 이름만 다르고 plugin 내부의 `skills/`를 공유할 수 있다. 다음 결합 구조는 두 문서에 각각 나온 규칙을 함께 적용한 cross-harness 구성이다.

```text
.agents/
└── plugins/
    └── marketplace.json          # Codex catalog
.claude-plugin/
└── marketplace.json              # Claude catalog
plugins/
└── graphori/
    ├── .codex-plugin/
    │   └── plugin.json
    ├── .claude-plugin/
    │   └── plugin.json
    └── skills/
        ├── graphori/
        │   └── SKILL.md
        ├── graphori-solo/
        │   └── SKILL.md
        └── graphori-dashboard/
            └── SKILL.md
```

예를 들어 두 marketplace의 최상위 `name`을 `graphori-marketplace`, plugin 이름을 `graphori`로 정하면 README의 복사 가능한 기본 설치는 다음처럼 분리된다.

```bash
# Codex
codex plugin marketplace add dotoricode/graphori
codex plugin add graphori@graphori-marketplace
```

```bash
# Claude Code
claude plugin marketplace add dotoricode/graphori
claude plugin install graphori@graphori-marketplace --scope user
```

설치 후 plugin skill 호출은 Codex `$graphori:graphori`, Claude Code `/graphori:graphori`다. 기존 `$graphori`와 `/graphori` UX를 유지하려면 plugin 설치와 별도로 각 공식 사용자 skill 경로에 standalone 설치하는 fallback을 계속 제공해야 한다.

README는 공통 설치 블록 하나가 아니라 `Codex`와 `Claude Code`를 최상위로 나누고, 각 섹션에서 네이티브 plugin 설치를 먼저 제시한 뒤 직접 복사 또는 bundled installer를 fallback으로 두는 것이 좋다. `gh repo clone`은 contributor/development 설치에 남기되 일반 사용자의 첫 명령으로 두지 않는 편이 조사된 주요 저장소들과 일치한다.
