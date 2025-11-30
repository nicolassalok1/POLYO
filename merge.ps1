Param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("to-trunk", "to-branch")]
    [string]$Mode
)

$ErrorActionPreference = "Stop"

Write-Host "`n=== POLYO MERGE SCRIPT (TRUNK VERSION) ===`n"

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

Write-Host "Fetching remote..."
git fetch origin

# Check branches
$localBranches = git branch --format="%(refname:short)"

if (-not ($localBranches -match "trunk")) {
    Write-Error "Branch 'trunk' does not exist locally."
    exit 1
}

if (-not ($localBranches -match "MGMN_before_merge")) {
    Write-Error "Branch 'MGMN_before_merge' does not exist locally."
    exit 1
}

switch ($Mode) {

    "to-trunk" {
        Write-Host "`n--- MERGE: MGMN_before_merge → trunk ---`n"

        git checkout trunk
        git pull origin trunk
        git merge MGMN_before_merge --no-edit

        Write-Host "`nPushing trunk..."
        git push origin trunk

        Write-Host "`n✔ Merge MGMN_before_merge → trunk completed."
    }

    "to-branch" {
        Write-Host "`n--- MERGE: trunk → MGMN_before_merge ---`n"

        git checkout MGMN_before_merge
        git pull origin MGMN_before_merge
        git merge trunk --no-edit

        Write-Host "`nPushing MGMN_before_merge..."
        git push origin MGMN_before_merge

        Write-Host "`n✔ Merge trunk → MGMN_before_merge completed."
    }
}

Write-Host "`n=== DONE ===`n"
