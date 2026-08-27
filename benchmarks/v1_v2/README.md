# Graphori v1과 v2 성능 측정 자료

2026-08-24에 진행한 비교 시험의 규칙, 실행 도구, 원본 숫자와 최종 보고서를
모아 둔 폴더다.

- [`PROTOCOL.md`](PROTOCOL.md): 두 버전을 어떻게 공정하게 비교했는지 설명
- [`PROTOCOL.en.md`](PROTOCOL.en.md): English protocol and limitations
- [`REPORT.md`](REPORT.md): 사람이 읽기 쉬운 최종 결과
- [`REPORT.en.md`](REPORT.en.md): English result summary
- [`raw-results.json`](raw-results.json): 처음 저장된 원본 결과
- [`results.json`](results.json): 집계 도구 오류를 바로잡은 결과
- [`run_benchmark.py`](run_benchmark.py): 매번 새 작업장을 만들어 시험하는 도구
- [`analyze_results.py`](analyze_results.py): 표와 보고서를 다시 만드는 도구
- [`verify_results.py`](verify_results.py): 숫자가 원본과 맞는지 확인하는 도구

다시 측정하려면 비교할 v2 소스 위치를 직접 지정한다.

```bash
python3 benchmarks/v1_v2/run_benchmark.py \
  --v2-source /path/to/graphori-v2 \
  --repetitions 2 \
  --output benchmarks/v1_v2/raw-results.json
python3 benchmarks/v1_v2/analyze_results.py
python3 benchmarks/v1_v2/verify_results.py
```

모델, 과제 또는 비교 규칙을 바꿨다면 기존 결과를 덮어쓰지 말고 날짜가 다른 새
결과 파일을 만든다.
