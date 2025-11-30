Param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("to-main", "to-branch")]
    [string]$Mode
)

$ErrorActionPreference = "Stop"

Write-Host "`n=== POLYO MERGE SCRIPT ===`n"

# Ensure we are in a git repo
if (-not (Test-Path ".git")) {
    Write-Error "Not inside a Git repository."
    exit 1
}

# Ensure working tree is clean
$gitStatus = git status --porcelain
if ($gitStatus) {
    Write-Error "Working tree is dirty. Commit or stash before merging."
    exit 1
}

# Fetch updates
Write-Host "Fetching remote..."
git fetch origin

# Ensure branches exist locally
$localBranches = git branch --format="%(refname:short)"
if (-not ($localBranches -match "main")) {
    Write-Error "Branch 'main' does not exist locally."
    exit 1
}
if (-not ($localBranches -match "MGMN_before_merge")) {
    Write-Error "Branch 'MGMN_before_merge' does not exist locally."
    exit 1
}

switch ($Mode) {

    "to-main" {
        Write-Host "`n--- MERGE: MGMN_before_merge → main ---`n"
        git checkout main
        git pull origin main
        git merge MGMN_before_merge --no-edit

        Write-Host "`nPushing main..."
        git push origin main

        Write-Host "`n✔ Merge MGMN_before_merge → main completed."
    }

    "to-branch" {
        Write-Host "`n--- MERGE: main → MGMN_before_merge ---`n"
        git checkout MGMN_before_merge
        git pull origin MGMN_before_merge
        git merge main --no-edit

        Write-Host "`nPushing MGMN_before_merge..."
        git push origin MGMN_before_merge

        Write-Host "`n✔ Merge main → MGMN_before_merge completed."
    }
}

Write-Host "`n=== DONE ===`n"
