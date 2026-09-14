# Snapshot — validation overlay 14 Sep 2026 (v4 freeze)

**Do not edit files in this folder.** Copy them out when you need to restore.

This folder was **refreshed** after overlay v44 (centered Gaussian on MCP/IP/TIP) and player 32.44 (no paint lag). Use this as the restore point for the next edit.

| Piece | Frozen at |
|---|---|
| Live player | `main.c85d1d13.js` + `main.23ef7b0e.css` (`nl-version` **32.44**) |
| Overlay JSON | v44 |
| Hugging Face | `e725a54` |
| GitHub at copy | `b69bb4f` |

Restore:

```bash
python3 REFERENCE_SNAPSHOT_2026-09-14_validation_overlay/restore.py --hf-root /path/to/hf-space
```

Tags: `backup/2026-09-14-validation-overlay-v4` (GitHub), `backup-2026-09-14-validation-overlay-v4` (HF).
