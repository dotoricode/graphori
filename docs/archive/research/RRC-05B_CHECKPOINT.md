# RRC-05B checkpoint

## Status

RRC-05B is complete. The benchmark ran 24 paired AB/BA live samples across
Direct Codex and Direct Claude for W2, W3, and W4. It did not change routing,
automatic Skill binding, or adaptive policy.

## Reproduction

```bash
python scripts/tdd_skill_benchmark.py --resume
```

The runner writes `RRC-05B_RESULTS.json` after every sample, so an interrupted
run resumes without repeating completed provider calls.

## Fixed identities

- Codex: `gpt-5.6-luna`, medium
- Claude: `claude-sonnet-5`, medium
- TDD package revision:
  `local-sha256:020e48193f19c303f462ac6c6bf16548f10e3b1f706df562f8fb8f6b3efb43a6`
- Installed snapshot digest:
  `sha256:f7762d76e11000f502a707b08f3ef292cd13c5e752c2d3bb38a66b69ce9c82f2`

The user-local package is not a Git checkout. `source_commit` is therefore
`null`; the immutable package and installed snapshot digests are authoritative.

## Decisions

- Fast/simple Nodes keep TDD disabled.
- Codex TDD is not an automatic candidate for W2, W3, or W4.
- Claude W4 is manual-only: mutation detection improved from 1/2 to 2/2, but
  median TTUR increased by 19.7% and escaped defects remained zero.
- No SkillPolicyEngine or ModelRouter policy was changed.

## Resume point

The next task must start from the completed RRC-05B artifacts and must not
repeat these live samples unless the provider/model/Skill identity changes or
the user explicitly requests a rerun.
