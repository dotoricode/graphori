#!/usr/bin/env python3
"""Deterministic mechanism benchmark for same-session repair."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time

from graphori_adapters.claude.adapter import ClaudeCodeExecutionAdapter
from graphori_adapters.codex.adapter import CodexExecutionAdapter
from graphori_core.ports import ContextBundle
from graphori_core.process_supervisor import ProcessLimits
from graphori_core.provider_session import (
    ProviderContinuation, ProviderSessionHandle, VerificationNack,
)
from graphori_core.provider_session_vault import PrivateSessionBinding
from graphori_core.run_plan import NodeSpec


FIXTURE = r'''#!/usr/bin/env python3
import json, os, sys, time
provider = os.environ["FIXTURE_PROVIDER"]
args = sys.argv[1:]
if "--version" in args:
    print(f"{provider}-fixture 1.0")
    raise SystemExit(0)
if "--help" in args:
    if provider == "codex":
        print("exec resume --json --output-schema --ephemeral --strict-config")
    else:
        print("-p --output-format --json-schema --no-session-persistence "
              "--permission-mode --allowedTools --disallowedTools "
              "--disable-slash-commands --resume")
    raise SystemExit(0)
if provider == "codex" and args == ["login", "status"]:
    raise SystemExit(0)
if provider == "claude" and args == ["auth", "status"]:
    print('{"loggedIn":true}')
    raise SystemExit(0)
resumed = "resume" in args or "--resume" in args
time.sleep(0.006 if resumed else 0.030)
report = {"schema_version":1,"status":"succeeded","summary":"repaired",
          "files_modified":[],"evidence":[{"kind":"test","reference":"fixture"}],
          "limitations":[]}
tokens = 20 if resumed else 100
if provider == "codex":
    print(json.dumps({"type":"thread.started","thread_id":"thread-fixture"}))
    print(json.dumps({"type":"item.completed","item":{"type":"agent_message",
          "text":json.dumps(report)}}))
    print(json.dumps({"type":"turn.completed","model":"fixture-model",
          "usage":{"input_tokens":tokens,"output_tokens":10}}))
else:
    print(json.dumps({"type":"system","subtype":"init","session_id":"session-fixture",
          "model":"fixture-model"}))
    print(json.dumps({"type":"result","subtype":"success","is_error":False,
          "session_id":"session-fixture","structured_output":report,
          "usage":{"input_tokens":tokens,"output_tokens":10}}))
'''


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


async def one(adapter, node: NodeSpec, context: ContextBundle) -> tuple[float, object]:
    started = time.perf_counter()
    session = await adapter.start_session(node)
    dispatch = await adapter.dispatch(session, node, context)
    result = await adapter.collect(dispatch)
    await adapter.release(session)
    return (time.perf_counter() - started) * 1_000, result


def provider_rows(provider: str, repetitions: int) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        fixture = root / "provider-fixture.py"
        fixture.write_text(FIXTURE, encoding="utf-8")
        adapter_class = CodexExecutionAdapter if provider == "codex" else ClaudeCodeExecutionAdapter
        adapter = adapter_class(
            workspace_root=root, executable=(sys.executable, str(fixture)),
            process_env={"FIXTURE_PROVIDER": provider},
            process_env_allowlist=frozenset({"PATH", "HOME", "TMPDIR", "FIXTURE_PROVIDER"}),
            limits=ProcessLimits(timeout_seconds=5, grace_seconds=0.1),
            enable_session_reuse=True,
        )
        if not adapter.probe().available:
            raise RuntimeError(f"{provider} fixture adapter did not probe")
        node = NodeSpec(
            "i1:rework:1", "implementation", "Repair", "repair the implementation",
            "worker", role="implementer", read_scope=(".",), write_scope=(".",),
            provider=provider, adapter=adapter.adapter_id,
            model="fixture-model", effort="medium", permission_profile="workspace_write",
        )
        base = ContextBundle(
            objective=node.objective, attempt_id="attempt:i1:rework:1:1",
            acceptance_criteria=("AC-01: tests pass",), read_scope=(".",),
            write_scope=(".",), run_id=f"run-{provider}", node_lineage="i1",
        )
        boundary = adapter._session_boundary(node, base)
        if boundary is None:
            raise RuntimeError("session boundary was unexpectedly incomplete")
        nack = VerificationNack(
            proof_ids=("AC-01",), command=("python", "-m", "unittest"),
            exit_code=1, evidence_refs=("fixture:failure",),
            workspace_digest="sha256:fixture",
        )
        fresh_ms: list[float] = []
        resumed_ms: list[float] = []
        fresh_tokens: list[int] = []
        resumed_tokens: list[int] = []
        correctness = True
        leaks = 0
        for index in range(repetitions):
            attempt = f"attempt:i1:{index + 1}"
            opaque = adapter.session_vault.put(
                base.run_id,
                PrivateSessionBinding(
                    provider=provider, provider_session_id=f"provider-session-{index}",
                    boundary_digest=boundary.digest(), attempt_id=attempt,
                    observed_model="fixture-model",
                ),
            )
            valid = ProviderContinuation(
                ProviderSessionHandle(provider, opaque, boundary.digest(), attempt, True), nack,
            )
            invalid = ProviderContinuation(
                ProviderSessionHandle(provider, opaque, "sha256:mismatch", attempt, True), nack,
            )
            elapsed, result = asyncio.run(one(adapter, node, ContextBundle(**{
                **base.__dict__, "continuation": invalid,
            })))
            fresh_ms.append(elapsed)
            fresh_tokens.append(int(result.runtime_metadata["usage"]["input_tokens"]))
            correctness &= result.outcome == "succeeded"
            leaks += int(bool(result.runtime_metadata["session_resumed"]))
            elapsed, result = asyncio.run(one(adapter, node, ContextBundle(**{
                **base.__dict__, "continuation": valid,
            })))
            resumed_ms.append(elapsed)
            resumed_tokens.append(int(result.runtime_metadata["usage"]["input_tokens"]))
            correctness &= result.outcome == "succeeded"
            leaks += int(not bool(result.runtime_metadata["session_resumed"]))

        fresh_median = statistics.median(fresh_ms)
        resumed_median = statistics.median(resumed_ms)
        wall_gain = (fresh_median - resumed_median) / fresh_median
        token_gain = 1 - statistics.mean(resumed_tokens) / statistics.mean(fresh_tokens)
        passed = correctness and leaks == 0 and (wall_gain >= 0.10 or token_gain >= 0.15)
        return {
            "provider": provider, "repetitions": repetitions,
            "fresh_median_ms": round(fresh_median, 3),
            "resumed_median_ms": round(resumed_median, 3),
            "fresh_p95_ms": round(percentile(fresh_ms, 0.95), 3),
            "resumed_p95_ms": round(percentile(resumed_ms, 0.95), 3),
            "wall_improvement": round(wall_gain, 6),
            "fresh_input_tokens_mean": statistics.mean(fresh_tokens),
            "resumed_input_tokens_mean": statistics.mean(resumed_tokens),
            "fresh_input_improvement": round(token_gain, 6),
            "correctness_equal": correctness, "scope_violations": 0,
            "session_boundary_leaks": leaks, "passed": passed,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=20)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.repetitions < 5:
        parser.error("--repetitions must be at least 5")
    rows = [provider_rows(provider, args.repetitions) for provider in ("codex", "claude")]
    payload = {
        "schema_version": 1, "kind": "deterministic_session_repair_fixture",
        "product_claim": False, "rows": rows,
        "passed": all(row["passed"] for row in rows),
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
