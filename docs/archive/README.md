# Archive

Working records from Graphori's development, kept because the claims in the
public documents point back at them. Nothing here is maintained, and none of it
describes the current API.

If you are reading Graphori for the first time, start at the
[product guide](../public/README.md) instead.

| Directory | What it holds |
| --- | --- |
| [`verification/`](verification/README.md) | Build reports and cross-model reviews for each implementation stage |
| [`research/`](research/README.md) | Routing experiments, checkpoints, and the measurements behind the defaults |
| [`design/`](design/README.md) | Architecture proposals, including ones that were not adopted |
| [`evidence/doctori/`](evidence/doctori/README.md) | Preserved records from Doctori, the predecessor project, with SHA-256 digests |

`PUBLIC_TREE_MANIFEST.json` lists the files and hashes of the `0.1.0` public
export. Regenerate it with `python scripts/export_public_tree.py`.

Two caveats on reading these documents:

A plan is not a result. Several files describe intended behavior that was later
changed or dropped — the Fast Mode notes in `design/` are the clearest example.
Where a document has no recorded execution, treat it as a proposal.

The Doctori evidence is from a different codebase. Its Windows and junction
audits say what Doctori's implementation did, not what Graphori's adapters do.
A few of its cross-references point at documents that were never published;
those appear as plain filenames rather than links.
