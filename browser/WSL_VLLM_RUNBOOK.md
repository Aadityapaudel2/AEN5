# WSL / Linux vLLM Runbook

Use this when the public Athena V5 portal is running on Windows.

Native Windows should not be treated as a host that boots `vllm` directly. Instead:

1. Run the vLLM server in WSL or Linux.
2. Point the Windows portal at that endpoint with `ATHENA_VLLM_BASE_URL`.

Important:
- a real Linux distro such as `Ubuntu` is required
- `docker-desktop` alone is not a valid WSL target for Athena vLLM
- if `wsl -l -v` only shows Docker-managed distros, install one first:

```powershell
wsl --install -d Ubuntu
```

After installing Ubuntu, launch it once manually before using Athena:

```powershell
wsl -d Ubuntu
```

On first launch, Ubuntu may ask you to finish initial setup and create a Linux user. Complete that once, then return to PowerShell.

Inside Ubuntu, ensure Python and `vllm` are actually installed before expecting `run_portal.ps1` to work:

```bash
python3 --version
python3 -m pip show vllm
```

If `vllm` is missing, create a Linux-home virtual environment and install it there. Do not install a heavy WSL venv under `/mnt/d/...`; big package writes can fail on the Windows-mounted filesystem. Athena will auto-detect `~/.athena_vllm/bin/python` on later runs:

```bash
python3 -m venv ~/.athena_vllm
~/.athena_vllm/bin/python -m pip install --upgrade pip
~/.athena_vllm/bin/python -m pip install vllm
```

## Example model path

Windows path:

```text
D:\AthenaPlayground\AthenaV5\models\Qwen3.5-4B
```

Typical WSL path:

```text
/mnt/d/AthenaPlayground/AthenaV5/models/Qwen3.5-4B
```

## Example start command inside WSL / Linux

```bash
python3 -m vllm.entrypoints.openai.api_server \
  --host 0.0.0.0 \
  --port 8001 \
  --model /mnt/d/AthenaPlayground/AthenaV5/models/Qwen3.5-4B \
  --served-model-name Qwen3.5-4B \
  --api-key athena-local \
  --trust-remote-code
```

If you prefer a different served model name, set the same name in:

```text
ATHENA_VLLM_MODEL
```

## Windows portal side

Set:

```powershell
$env:ATHENA_VLLM_BASE_URL = "http://127.0.0.1:8001/v1"
```

Then run:

```powershell
Set-Location D:\AthenaPlayground\AthenaV5
.\run_portal.ps1 -PreflightOnly
.\run_portal.ps1
```

`run_portal.ps1` is the canonical public entrypoint. It will call the shared vLLM bootstrap internally when needed.

If you want to inspect the runtime separately, you can still use:

```powershell
.\run_vllm.ps1 -Status
```

## Expected result

- preflight passes
- `/healthz` reports:
  - `ok: true`
  - `ready: true`
  - `runtime_backend: vllm_openai`
- the Windows portal reuses the healthy external vLLM endpoint instead of trying to bootstrap a native Windows sidecar
