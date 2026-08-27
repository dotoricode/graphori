# v1에서 v2까지의 이력과 근거

비공개 개발 저장소에는 원래 commit 이력이 보존되어 있습니다. 공개 저장소는 검토된 source snapshot에서 시작하므로 아래 commit은 공개 저장소에서 직접 이동할 수 있는 이력이 아니라 export 문서에 남긴 식별값입니다.

- `d6a3fa5` — 학습 게임 dashboard 작업
- `f888c0b`, `eb382f4` — pixel office dashboard 작업
- `773906b` — v2 execution engine과 verification 흐름
- `5185a18` — live office 화면과 dashboard skill
- `4c09517` — 성능 측정·검증 근거 추가

commit subject와 `docs/verification/`, `docs/research/` 기록은 provenance 단서이지 독립 audit가 아닙니다. fixture, local run, 설계 비교를 다룬 기록도 있으므로 reliability·cost·agent 품질 주장으로 바꾸면 안 됩니다. 공개 베타가 재현 가능한 benchmark schema를 추가하는 이유도 과거 근거가 통제된 benchmark가 아니기 때문입니다.
