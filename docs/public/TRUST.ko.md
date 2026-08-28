# 신뢰 모델

Graphori는 append-only local journal과 결정론적 reducer를 run의 기록으로 봅니다. replay는 저장된 event가 같은 projection과 digest를 만드는지 보여 줄 수 있습니다. agent의 텍스트가 참인지, command가 안전했는지, run 뒤 working tree가 옳은지를 증명하지는 않습니다.

| Graphori가 기록하는 것 | 사람 또는 외부 통제가 결정할 것 |
| --- | --- |
| plan node·의존성·route 선택·event·deterministic verifier의 exit 근거 | 범위 적절성·provider 권한·secret 처리·review·배포 |
| 기록된 digest chain과 pinned metadata의 일치 | provider가 요청을 올바르게 이해했는지 |
| 안전한 replay가 불가능할 때 blocked/unknown 상태 | 모호한 외부 작업을 재시도·승인·폐기할지 |

자격 증명은 objective, journal, evidence label, command에 넣지 마세요. Graphori는 sandbox가 아닙니다. 좁은 write scope, 명시적 verification, version control, human gate를 사용하세요.
