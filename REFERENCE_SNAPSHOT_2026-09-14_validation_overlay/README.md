# Snapshot — validation overlay 14 Sep 2026 (v3 freeze)

**Do not edit files in this folder.** Copy them out when you need to restore.

This folder was **refreshed** after overlay v42 (joints on MCP/IP/TIP with 1€ smoothing). Use this as the restore point for the next edit (zero-lag).

| Piece | Frozen at |
|---|---|
| Live player | `main.a0625928.js` + `main.23ef7b0e.css` (`nl-version` **32.43**) |
| Overlay JSON | v42 |
| Hugging Face | `7661a27` |
| GitHub at copy | `de3844a` |

Restore:

```bash
python3 REFERENCE_SNAPSHOT_2026-09-14_validation_overlay/restore.py --hf-root /path/to/hf-space
```

Tags: `backup/2026-09-14-validation-overlay-v3` (GitHub), `backup-2026-09-14-validation-overlay-v3` (HF).
