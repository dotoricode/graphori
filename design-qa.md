# Graphori Live Office Design QA

## Comparison target

- Source visual truth: the six pixel-character references supplied in the conversation:
  - `/var/folders/bk/3mxkf8t509dfnfs5b911qms80000gn/T/orca-paste-1786342662521-0a1c0778-381a-4bc0-8247-83804544c732.png` (320 × 297)
  - `/var/folders/bk/3mxkf8t509dfnfs5b911qms80000gn/T/orca-paste-1786342684560-86a0fa43-9e43-42b6-8f4c-94caf9a244e3.png` (736 × 736)
  - `/var/folders/bk/3mxkf8t509dfnfs5b911qms80000gn/T/orca-paste-1786342697341-56481193-c975-44a6-88b3-590ebdd89bd2.png` (1200 × 1200)
  - `/var/folders/bk/3mxkf8t509dfnfs5b911qms80000gn/T/orca-paste-1786342705238-73ef68eb-0c99-466f-ac89-709a208590c5.png` (736 × 736)
  - `/var/folders/bk/3mxkf8t509dfnfs5b911qms80000gn/T/orca-paste-1786342716416-c3d4ee6c-5e59-4962-bca9-2c1c845d47e2.png` (736 × 736)
  - `/var/folders/bk/3mxkf8t509dfnfs5b911qms80000gn/T/orca-paste-1786342733658-00662121-f52e-42b7-a064-502a02b3d85e.png` (735 × 804)
- Implementation URL: `http://127.0.0.1:8765/`
- Historical browser print render: [docs/dashboard/qa/live-office-browser-print.png](docs/dashboard/qa/live-office-browser-print.png) (the previous standing-character revision).
- Current state endpoint: `run-dashboard`, six verified nodes out of six.
- Current visual capture status: unavailable because the app browser reported no available browser instances during this revision's QA.

## Full-view comparison evidence

The current implementation uses six distinct 2 × 2 raster sprite sheets. Every frame keeps the worker seated with the same desk and chair while the work prop changes: console and plan, book page, blueprint pen, two different keyboards, or QA checklist. Each sheet was inspected at 512 × 512 after chroma-key removal; all four quadrants contain transparency and every neighboring frame has a non-zero image difference.

The office remains one connected five-zone map. The live server successfully served the updated HTML and all new sprite assets, and the snapshot endpoint still returned the real completed run state.

## Focused-region evidence

The six sprite sheets were inspected directly at their committed resolution. A current full-page comparison cannot be completed until an app browser instance is available again; the existing comparison images must be treated as historical rather than evidence for the seated-character revision.

## Required fidelity surfaces

- Fonts and typography: `Gothic A1` is the only requested webfont and is used for headings, labels, controls, telemetry, and body copy. Heading sizes stay below 2.8 rem and do not reproduce the oversized display typography rejected by the user.
- Spacing and layout: four compact telemetry cards precede one 16:9 office map. Labels remain inside their role zones with no measured overlap. Small screens use a contained horizontal office viewport instead of breaking the page.
- Colors and tokens: the UI uses a restrained navy, teal, amber, violet, green, and coral palette that matches the generated office and keeps active, waiting, passed, and blocked states distinct.
- Image quality and asset fidelity: the office and six unique seated workers are raster PNG assets. Worker sheets have alpha backgrounds, retain hard pixel edges, and use nearest-neighbor rendering. No CSS-drawn replacement avatars or standing-character assets remain.
- Copy and content: the copy describes live work, verified progress, and current sessions. It does not describe the dashboard as Graphori's primary product.
- States and interactions: run selection, reconnect, empty state, fresh activity, stale pause, passed, blocked, multiple sessions, progress, and reduced-motion behavior are implemented. Working state advances through four task frames without moving the entire character left, right, or up.
- Accessibility: the run control has a label and focus indicator; map stations expose text alternatives; the decorative worker images are hidden from assistive technology; reduced motion is supported.

## Comparison history

1. Earlier implementation — P1: an empty run replaced the whole office with a sentence, and avatars were CSS shapes inside status cards. Fix: added an always-visible shared office map and five raster worker assets; planning now remains active from startup.
2. First live-state check — P2: stale worker nodes could remain animated because their last per-node heartbeat was cached. Fix: worker activity now stops when the global run liveness becomes stale; planning continues managing the dashboard.
3. Post-fix check: DOM inspection found no caption overlap or missing images. Fresh state computed `plan-patrol`, `implement-type`, and `verify-inspect`, with two implementation workers rendered concurrently. The browser console contained no errors.
4. Seated-work revision: replaced all standing PNGs and transform sway animations with six unique seated sprite sheets. Planning operates a console, research turns a page, design draws, implementation types with two different people, and verification inspects and marks a checklist. All typography now uses `Gothic A1`.

## Findings

- [P2] Current viewport screenshot evidence is unavailable.
  - Location: app browser discovery.
  - Evidence: browser setup succeeded, but the available-browser list was empty.
  - Impact: sprite sheets, code, HTTP delivery, and tests were verified, but the final integrated office layout cannot be compared pixel-for-pixel in this revision.
  - Fix: reopen the dashboard in the app browser, capture a working multi-team state, and repeat the reference comparison.

## Implementation checklist

- [x] Always show one connected five-zone company map.
- [x] Keep planning active before run events exist.
- [x] Bind each team to real node state and liveness.
- [x] Show concurrent sessions as multiple workers in one team zone.
- [x] Never duplicate one visible character when a role has multiple sessions.
- [x] Keep every worker seated with a role-specific hand or prop animation.
- [x] Use one font family throughout the dashboard.
- [x] Prevent caption overlap and page overflow.
- [x] Verify sprite frame differences, transparency, transport, JavaScript syntax, and tests.
- [ ] Repeat visual QA with an exact browser screenshot when an app browser instance is available.

final result: blocked
