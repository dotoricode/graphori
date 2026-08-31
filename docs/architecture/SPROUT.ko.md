# Graphori Sprout

**하나를 먼저 실행하고 검증한 뒤, 통과한 흐름만 확장합니다.**

Sprout는 Graphori의 선택형 증거 기반 실행 정책입니다. 노드가 끝났다는 사실만으로 다음
작업을 열지 않습니다. 저장된 산출물이 선언된 검증 의무를 닫아야 다음 전이 권한이
생깁니다.

## 왜 필요한가

고정 그래프는 현재 경로가 유효한지 알기 전에 후속 분기 비용부터 씁니다. Sprout는 가장
작은 end-to-end 파일럿을 먼저 입증한 뒤, 아직 열린 검증 의무를 닫는 노드만 실행합니다.
많은 자원을 투입하는 대신 구조를 바꿔 같은 품질을 더 적은 계산으로 얻으려는 설계입니다.

DeepSeek와의 연결은 제한적입니다. Graphori가 모델을 학습시키는 것은 아닙니다. 필요한
전문가만 활성화하는 희소 실행과, 신뢰할 수 있는 규칙 기반 판정을 다음 선택에 사용하는
사고방식만 실행 시스템으로 옮겼습니다.

## 핵심 불변식

> 열림·실패·판단 불가 상태의 검증 의무가 있는 산출물은 fan-in이나 commit을 열 수
> 없습니다. 동적으로 확장되는 모든 노드는 이름이 붙은 의무를 하나 이상 닫아야 합니다.

산출물에는 payload 참조, 원본 계보, 주장, 검증 의무, 판정 결과, 증거 참조가 함께
들어갑니다. 실행자는 agent, process, verifier, control, human 중 무엇이어도 됩니다.

## 세 가지 권한

- `EXPAND`: 파일럿이 통과해야 불변 plan revision을 추가합니다.
- `FAN_IN`: 통과한 분기 산출물만 합성 입력으로 들어갑니다.
- `COMMIT`: 합성까지 통과해야 되돌릴 수 있는 외부 효과를 냅니다. 되돌릴 수 없는
  Sprout commit은 이번 버전에서 거부합니다.

`ProofFrontier.route`는 branch budget 안에서 열린 의무를 모두 닫는 후보 조합을
결정적으로 찾습니다. 병렬 critical-path 비용, 전체 비용, 노드 수 순서로 최소화합니다.
실패는 해당 의무만 고치는 제한된 재작업으로, 판단 불가는 사람에게 보냅니다. 결정은
canonical JSON과 digest를 가져 같은 입력에서 재생됩니다.
정확 탐색은 기본적으로 후보 32개와 branch budget 4 이하로 제한합니다. 더 큰 탐색은
운영실 시간을 끝없이 쓰지 않고 사람 판단으로 fail-closed 합니다.
`route_if_profitable`은 선언 비용, WIP, dependency, scope 충돌 조건으로 기존 static
경로와 파일럿+확장 경로를 비교합니다. 절대·비율 최소 이득을 못 넘으면 `use_static`을
반환하므로 희소 실행을 무조건 강제하지 않습니다. `authorize`는 순수 planning
판정기이며, 전달받은 trusted digest 집합은 호출자 소유의 신뢰 경계이지 Graphori가
journal을 읽었다는 증거가 아닙니다.

`plan_shadow`는 실제 실행을 항상 v2로 유지하고 Sprout 대안의 불변 telemetry만
돌려줍니다. `plan_conditionally`만 명시적 opt-in 활성화 경로입니다. 대상이 4개
이상이고 독립성이 명시됐으며 v2 proof coverage가 완전하고 coverage가 줄지 않고
dependency·scope 충돌과 planning 불확실성이 없으며 절대·상대 이득 기준을 모두 넘을
때만 Sprout를 선택합니다. 하나라도 알 수 없으면 v2를 선택합니다.

## 현재 범위와 한계

`NodeSpec.requires_proofs`가 실행을 막고, `closes_proofs`가 canonical PASS로 닫히는
의무를 선언합니다. 온라인 학습, 범용 proof DSL, verifier 자동 생성, 분산 graph rewrite,
정책 자동 승격은 넣지 않았습니다.

`proof_policy="sprout-1"`인 plan은 producer 존재, proof가 완전한 fan-in, proof gate가
있는 되돌릴 수 있는 외부 commit을 실제 scheduler, execution engine, journal 경로에서
강제합니다. 다만 동적 `EXPAND`와 성능 gate는 현재 core API를 직접 사용하는 선택 기능입니다. 기본 CLI compiler는
proof obligation을 추측하거나 실행 중인 plan을 자동으로 다시 쓰지 않습니다. 호출자가
artifact 신뢰 경계를 세우고 proof contract를 명시해야 합니다.

Sprout는 선언된 의무가 빠짐없이 집행됐다는 것만 보장합니다. 계약 자체에 중요한 의무가
빠졌다면 진실을 보장할 수 없습니다. 주관적인 작업은 `unknown`으로 남겨 human gate로
보내야 합니다. 정책 벤치마크의 시간은 모델링 값이며 provider 실측 시간이나 토큰이
아닙니다.

[English](SPROUT.md) · [벤치마크](../../benchmarks/sprout/REPORT.ko.md)
