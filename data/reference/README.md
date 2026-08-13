# Reference environment

Only promote a snapshot captured by `scripts/scan_gh_components.py` from a real
Rhino/Grasshopper session. Keep the machine-local current snapshot at
`data/component_library.json`; copy an intentionally reviewed full snapshot to
`data/reference/component_snapshot.json` when establishing or updating the
shared compatibility baseline.

The compiler never scans Grasshopper. It compares an explicit current snapshot
with this reference through the offline `health` command.
