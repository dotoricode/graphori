# v1에서 v2까지의 이력과 근거

이 저장소는 과거를 release claim으로 다시 부르지 않고 보존합니다. reachable commit에는 v1 시각화·학습 작업 뒤 v2 engine 작업이 보입니다.

- `d6a3fa5` — 학습 게임 dashboard 작업
- `f888c0b`, `eb382f4` — pixel office dashboard 작업
- `773906b` — v2 execution engine과 verification 흐름
- `5185a18` — live office 화면과 dashboard skill
- `4c09517` — 성능 측정·검증 근거 추가

commit subject와 `docs/verification/`, `docs/research/` 기록은 provenance 단서이지 독립 audit가 아닙니다. fixture, local run, 설계 비교를 다룬 기록도 있으므로 reliability·cost·agent 품질 주장으로 바꾸면 안 됩니다. 공개 베타가 재현 가능한 benchmark schema를 추가하는 이유도 과거 근거가 통제된 benchmark가 아니기 때문입니다.
