# Athena V5 Portal

This folder contains the web deployment assets for the V5 portal route:

- `portal_server.py` (repo root): FastAPI server
- `templates/index.html`: UI shell
- `static/portal.css`: styles
- `static/portal.js`: client logic

## Route

Default path prefix:

- `/AthenaV5`

Override with:

- `ATHENA_PORTAL_PATH_PREFIX=/your/path`

## Local Start (smoke mode, no model load)

```powershell
Set-Location D:\AthenaPlayground\AthenaV5
.\run_portal.ps1
```

Open:

- `http://localhost:8000/AthenaV5`
- `http://localhost:8000/healthz`

## Local Start (live model)

```powershell
Set-Location D:\AthenaPlayground\AthenaV5
.\run_portal.ps1 -LoadModel
```

## Cloudflare Tunnel

Use the script:

```powershell
.\cloudflared_athenav5.ps1
```

Then browse:

- `https://portal.neohmlabs.com/AthenaV5`

Or run server + tunnel in one command:

```powershell
.\run_portal_v5.ps1
```

## Notes

- Smoke mode is default to avoid loading the model while CUDA is busy.
- Chat endpoint supports optional thinking toggles and returns full transcript HTML from server-side rendering.
