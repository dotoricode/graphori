# 동일 세션 재작업

동일 세션 재작업은 결정적 검증이 실패했을 때 모델이 이미 이해한 문맥을 선택적으로
재사용하는 지연시간 실험이다. 검증 판정 자체는 재사용하지 않는다.

`graphori run --same-session-repair ...`로 켠다. run, 노드 계보, 역할, 작업공간,
provider, 요청 model, effort, agent 계약, 도구 정책, 권한, 검증 판정이 가리키는 정확한
attempt가 모두 같을 때만 기존 구현 세션을 재개한다. NACK에는 proof ID, argv, 종료 코드,
작업공간 digest와 증거 참조만 들어가며 완료 기준을 약화할 권한은 없다.

Codex와 Claude의 실제 session ID는 capability이므로 journal에 기록하지 않는다. 권한
`0600`인 작업공간 전용 파일에 저장하고 journal에는 무작위 opaque handle과 binding
digest만 남긴다. 실행이 terminal 상태가 되면 private handle을 제거한다.

경계나 private binding이 없으면 NACK을 포함한 새 repair 세션을 시작한다. 반대로 resume를
실제로 시도한 뒤 timeout, 취소, nonzero, malformed output이 발생하면 자동 재실행하지
않는다. CLI 결과만으로 첫 turn의 외부 효과가 없었다고 증명할 수 없기 때문이다.

fixture benchmark의 합성 시간과 token은 메커니즘 검사이며 실제 provider 성능 수치가 아니다.
