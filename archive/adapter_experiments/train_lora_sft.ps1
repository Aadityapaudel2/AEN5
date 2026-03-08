param(
    [string]$ArgsFile = "Finetune/lora_args.json",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

function Resolve-PythonExe {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectRootPath
    )

    $Candidates = @()
    if ($env:VIRTUAL_ENV) {
        $Candidates += (Join-Path $env:VIRTUAL_ENV "Scripts\python.exe")
    }
    $Candidates += (Join-Path $ProjectRootPath ".venv\Scripts\python.exe")
    $ParentDir = Split-Path -Parent $ProjectRootPath
    if ($ParentDir) {
        $Candidates += (Join-Path $ParentDir ".venv\Scripts\python.exe")
    }

    foreach ($Candidate in $Candidates) {
        if ([string]::IsNullOrWhiteSpace($Candidate)) { continue }
        if (Test-Path -LiteralPath $Candidate) {
            return (Resolve-Path -LiteralPath $Candidate).Path
        }
    }

    $PythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($PythonCmd) {
        return $PythonCmd.Source
    }

    throw "Python executable not found. Activate a venv or create .venv in the project root."
}

$ResolvedArgsFile = if ([System.IO.Path]::IsPathRooted($ArgsFile)) {
    $ArgsFile
} else {
    Join-Path $ProjectRoot $ArgsFile
}
if (-not (Test-Path -LiteralPath $ResolvedArgsFile)) {
    throw "Args file not found: $ResolvedArgsFile"
}
$ResolvedArgsFile = (Resolve-Path -LiteralPath $ResolvedArgsFile).Path

$PythonExe = Resolve-PythonExe -ProjectRootPath $ProjectRoot
Write-Host "python_exe=$PythonExe"
Write-Host "args_file=$ResolvedArgsFile"

try {
    $Cfg = Get-Content -LiteralPath $ResolvedArgsFile -Raw | ConvertFrom-Json
} catch {
    throw "Failed to parse args JSON: $ResolvedArgsFile`n$($_.Exception.Message)"
}

function Add-AccelerateOption {
    param(
        [Parameter(Mandatory = $true)]
        [ref]$ArgsRef,
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [object]$Value
    )
    if ($null -eq $Value) { return }
    $Text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($Text)) { return }
    $ArgsRef.Value += @("--$Name", $Text)
}

$LaunchArgs = @("-m", "accelerate.commands.launch")
if ($Cfg.PSObject.Properties.Name -contains "accelerate") {
    Add-AccelerateOption -ArgsRef ([ref]$LaunchArgs) -Name "num_processes" -Value $Cfg.accelerate.num_processes
    Add-AccelerateOption -ArgsRef ([ref]$LaunchArgs) -Name "num_machines" -Value $Cfg.accelerate.num_machines
    Add-AccelerateOption -ArgsRef ([ref]$LaunchArgs) -Name "mixed_precision" -Value $Cfg.accelerate.mixed_precision
    Add-AccelerateOption -ArgsRef ([ref]$LaunchArgs) -Name "dynamo_backend" -Value $Cfg.accelerate.dynamo_backend
}

$LaunchArgs += @(
    (Join-Path $ScriptDir "lora_train.py"),
    "--args_file", $ResolvedArgsFile
)

if ($DryRun) {
    $Quoted = $LaunchArgs | ForEach-Object {
        if ($_ -match "\s") { '"' + $_ + '"' } else { $_ }
    }
    Write-Host "Dry run only. Command:"
    Write-Host ($PythonExe + " " + ($Quoted -join " "))
    return
}

& $PythonExe @LaunchArgs
