# Contributing

Small, evidence-backed changes are welcome. If a change moves a product
boundary, touches execution safety, or alters a public claim, open an issue
first so the discussion happens before the diff.

## Before you open a pull request

Run both checks:

```sh
python -m unittest discover -s tests -v
python scripts/validate_docs_indexes.py
```

The suite contains hundreds of tests and takes a couple of minutes. Some fixtures skip rather
than fail when the platform cannot support them — macOS-only image tools, and
symlink creation on Windows without Developer Mode. A skip is expected; a
failure is not.

The index check requires every directory that holds Markdown to have a
`README.md` naming each file in it. Add new documents to their directory index
in the same commit.

## What makes a change easy to accept

Keep the diff scoped to one thing, and leave existing user work alone.

Add or update tests when behavior changes. A test that would have failed before
your fix is worth more than three that pass either way.

Say what you actually ran in the pull request, and what you did not. Describing
a limitation costs nothing; discovering it after a merge is expensive.

Do not commit generated benchmark output, provider credentials, or any claim
that cannot be reproduced from this repository.

## License

By contributing you agree your contribution is licensed under the MIT License.
Participation is covered by the [Code of Conduct](CODE_OF_CONDUCT.md).
