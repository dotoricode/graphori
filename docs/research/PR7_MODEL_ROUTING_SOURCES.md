# PR7 model-routing source verification

Retrieved: 2026-08-14

Scope: official provider identities and availability surfaces for OpenAI Codex
CLI and Anthropic Claude Code, plus the user-supplied Artificial Analysis Coding
Agent Index v1.3 values. This note does not infer provider runtime model IDs from
benchmark labels.

## Identity rule

Graphori must store provider runtime identity and benchmark identity separately.

- **Provider runtime identity** is a model name or alias documented by the
  provider for an execution surface. Availability can still depend on account,
  provider, product version, or administrator policy.
- **Benchmark identity** is the harness/model/effort label published with a
  benchmark result. It identifies the measured configuration, not an executable
  model ID.

Confidence: **HIGH**. Both providers document model-selection aliases separately
from full model names, and Artificial Analysis reports results as agent-harness
variants.

## OpenAI Codex CLI runtime identity

OpenAI's Codex model documentation explicitly lists the following CLI selections:

| Display family | Codex CLI selection | Documented Codex CLI status | Confidence |
| --- | --- | --- | --- |
| GPT-5.6 Sol | `gpt-5.6-sol` | Recommended model; selectable with `codex -m` | HIGH |
| GPT-5.6 Terra | `gpt-5.6-terra` | Recommended model; selectable with `codex -m` | HIGH |
| GPT-5.6 Luna | `gpt-5.6-luna` | Recommended model; selectable with `codex -m` | HIGH |

The same page documents `gpt-5.6` as the default GPT-5.6 selection and shows
`codex exec -m gpt-5.6` for non-interactive runs. It describes the default Power
setting as GPT-5.6 Sol with medium reasoning, while the API model catalog states
that the `gpt-5.6` alias routes to `gpt-5.6-sol`. Supported GPT-5.6 reasoning
efforts in the API catalog are `none`, `low`, `medium`, `high`, `xhigh`, and
`max`.

Sources:

- [OpenAI Codex models](https://learn.chatgpt.com/docs/models)
- [OpenAI API model catalog](https://developers.openai.com/api/docs/models)
- [OpenAI Codex CLI reference](https://learn.chatgpt.com/docs/developer-commands?surface=cli)

Availability qualification: **MEDIUM** for any particular account at a specific
moment. The official page establishes Codex CLI model selections, but it also
distinguishes ChatGPT sign-in from API-key use and documents product-specific
retirements. PR7 should therefore discover actual availability through the
configured adapter/provider rather than treating this static note as entitlement
evidence.

## Anthropic Claude Code runtime identity

Anthropic's current Claude Code documentation supports aliases and full model
names. For the Anthropic API provider, the current aliases resolve as follows:

| Claude Code selection | Current Anthropic API resolution | Minimum Claude Code version | Confidence |
| --- | --- | --- | --- |
| `sonnet` | Claude Sonnet 5 | 2.1.197 for Sonnet 5 | HIGH |
| `opus` | Claude Opus 5 | 2.1.219 for Opus 5 | HIGH |
| `claude-sonnet-5` | Full model name for Claude Sonnet 5 | 2.1.197 | HIGH |
| `claude-opus-5` | Full model name for Claude Opus 5 | 2.1.219 | HIGH |

The Claude Code CLI accepts either an alias or full model name through
`--model`; Anthropic's example is `claude --model claude-sonnet-5`. Aliases are
not stable runtime identities: their resolution varies by provider and can
change over time. Anthropic recommends a full model name when pinning a version.
For example, as retrieved, `opus` resolves to Opus 5 on the Anthropic API but
to older models on some other providers; `sonnet` similarly varies by provider.

The first-party model pages confirm API identities `claude-sonnet-5` and
`claude-opus-5`. Therefore the earlier concern that Opus 5 lacked an official
provider identity is no longer true as of the retrieval date.

Sources:

- [Claude Code model configuration](https://code.claude.com/docs/en/model-config)
- [Claude Code CLI reference](https://code.claude.com/docs/en/cli-usage)
- [Claude models overview](https://platform.claude.com/docs/en/about-claude/models/overview)
- [What's new in Claude Sonnet 5](https://platform.claude.com/docs/en/about-claude/models/whats-new-sonnet-5)
- [What's new in Claude Opus 5](https://platform.claude.com/docs/en/about-claude/models/whats-new-opus-5)

Availability qualification: **HIGH** for documented Anthropic API identities and
Claude Code support; **MEDIUM** for a specific deployment because aliases,
administrator allowlists, cloud-provider enablement, and installed Claude Code
version can change what is executable.

## Artificial Analysis benchmark identity

Artificial Analysis identifies these as **Coding Agent Index v1.3 agent
variants**, pairing an agent harness with a benchmark model label and effort.
The index is a composite of DeepSWE, Terminal-Bench v2, and SWE-Atlas-QnA. Its
reported time is average active agent wall time and excludes environment startup,
verifier/judge time, and other harness overhead.

Ten of the user-supplied values exposed by the inspected publisher views are verified:

| Benchmark harness | Benchmark model label | Index | Time/task | Verification |
| --- | --- | ---: | ---: | --- |
| Codex | GPT-5.6 Luna (medium) | 42 | 3.4m | Confirmed |
| Codex | GPT-5.6 Terra (medium) | 48 | 4.3m | Confirmed |
| Codex | GPT-5.6 Terra (high) | 56 | 6.2m | Confirmed |
| Codex | GPT-5.6 Terra (xhigh) | 57 | 6.9m | Confirmed |
| Codex | GPT-5.6 Sol (medium) | 61 | 5.2m | Confirmed |
| Codex | GPT-5.6 Sol (high) | 64 | 6.3m | Confirmed |
| Codex | GPT-5.6 Sol (xhigh) | 65 | 7.4m | Confirmed |
| Claude Code | Opus 5 (medium) | 62 | 12.2m | Confirmed |
| Claude Code | Opus 5 (high) | 63 | 13.4m | Confirmed |
| Claude Code | Opus 5 (xhigh) | 67 | 23.6m | Confirmed |

The separately supplied `GPT-5.6 Luna (high) = 51 / 5.7m` value was not visible
in the inspected publisher views. The fixed snapshot retains it only as a
low-confidence prior; it must not be described as independently verified here.

Sources:

- [Artificial Analysis: Codex vs. Cursor CLI](https://artificialanalysis.ai/agents/coding-agents/comparisons/codex-vs-cursor-cli)
- [Artificial Analysis: Claude Code vs. Grok Build](https://artificialanalysis.ai/agents/coding-agents/comparisons/claude-code-vs-grok-build)
- [Artificial Analysis Coding Agent Index methodology](https://artificialanalysis.ai/methodology/coding-agents-benchmarking)

Confidence: **HIGH** that the table reproduces the publisher's v1.3 values;
**MEDIUM** for transferring those values to Graphori runtime predictions because
Graphori adds adapter startup, queueing, delivery, verification, and cleanup
overhead not included in the published active-agent time.

## PR7 implications

1. Use `RuntimeModel` entries sourced from provider discovery/documentation and
   separate `BenchmarkModel` entries sourced from Artificial Analysis.
2. Bind them explicitly; never derive `gpt-5.6-sol` or `claude-opus-5` by
   normalizing benchmark strings.
3. Treat Codex/Claude aliases as mutable routing conveniences, not pinned model
   identities.
4. Fail closed when adapter discovery cannot confirm that a documented model is
   available in the current account or provider.
5. Preserve benchmark harness, effort, version, and retrieval date in every
   benchmark binding.
