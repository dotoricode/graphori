# Reproducible examples

Run these from a checkout after installing the runtime.

```sh
repo_root="$(pwd -P)"
graphori plan "add a bounded change" --root "$repo_root" --lang en
graphori plan "범위가 정해진 변경을 추가해줘" --root "$repo_root" --lang ko
```

For a safe non-provider demonstration, use the existing test suite and dashboard fixture rather than claiming a live agent demo:

```sh
python -m unittest tests.test_product_entry -v
python scripts/dashboard_smoke.py
```

Showcase fixtures are specified under `minimal-fix/`, `parallel-research/`, `scope-protection/`, and `crash-resume/`. Their `expected.json` files intentionally say `not_recorded` until a disposable run produces real evidence.
