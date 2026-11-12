# Architecture

- `desk/server.py`: loopback HTTP host, Origin/Host checks, revision-protected persistence and atomic backup writes.
- `desk/desk.js`: notebook, independent answers, question snapshots, user navigation and font controls.
- `desk/immersive.js`: conversation adapter/UI state. Its current source is inlined in index.html for compatibility with older running hosts.
- `desk/storyboard.js`: durable layout records referencing media, pointer dragging and conflict preservation. Also inlined in index.html; keep copies synchronized when changing it.
- `desk/live-update.js`: client hash polling, state snapshots, composition guard and foreground-only focus restore.
- `desk/agent_bridge.py`, `chat_bridge.py`: bounded Codex processes and persisted results. Planning/conversation do not claim game implementation.
- `desk/production_manager.py`, `manager_modules`: local module scheduling, independent review jobs and explicit candidate write handoff.
- `desk/delivery.py`: evidence checks; no completion solely from elapsed time or answer count.
- `native/desk`: WinForms/WebView2 shell, panels, window placement, debug event codes and neutral IME policy.
- `native/notifier`: separate, single-instance nonactivating screen popup watcher.

## Important boundaries

This is a single-PC prototype, not a multi-user service. Keep it on loopback. Native/AI adapters currently target Windows. A code update may reload the web client; changing compiled shell code requires building/reopening. User data and profiles are outside replaceable native binaries. Backups do not replace an external disk backup. Storyboard data currently uses an internal question record; it is excluded from visible notebook pages.

The manager can review or modify only its configured candidate path after explicit handoff. Its local ownership checks do not replace OS permissions or an organization-wide reservation system. OnlyChat external dispatch is not implemented.
