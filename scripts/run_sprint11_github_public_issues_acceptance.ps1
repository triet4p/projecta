param(
    [string]$ApiBaseUrl = $env:PROJECTA_GITHUB_ACCEPTANCE_API_URL,
    [string]$ProjectHandle = $env:PROJECTA_GITHUB_ACCEPTANCE_PROJECT_HANDLE,
    [string]$Owner = $env:PROJECTA_GITHUB_ACCEPTANCE_OWNER,
    [string]$Repository = $env:PROJECTA_GITHUB_ACCEPTANCE_REPOSITORY,
    [string]$SetupHandle = $env:PROJECTA_GITHUB_ACCEPTANCE_SETUP_HANDLE,
    [string]$ProjectId = $env:PROJECTA_GITHUB_ACCEPTANCE_PROJECT_ID,
    [string]$ActorId = $env:PROJECTA_GITHUB_ACCEPTANCE_ACTOR_ID,
    [string]$ContextSecret = $env:PROJECTA_GITHUB_ACCEPTANCE_CONTEXT_SECRET,
    [string]$EvidencePath = "docs/sprint-plans/sprint-11/artifacts/s11-A18-github-live-acceptance.json",
    [string]$JourneyEvidencePath = "docs/sprint-plans/sprint-11/artifacts/s11-A18-github-live-journey.json"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$evidence = Join-Path $root $EvidencePath
$journeyEvidence = Join-Path $root $JourneyEvidencePath
$steps = [System.Collections.Generic.List[object]]::new()
$startedAt = [DateTime]::UtcNow
$status = "failed"
$failure = $null
$installation = $null
$enabledInstallation = $null
$enabled = $false
$snapshot = $null
$continuity = $null
$baselineRun = $null
$replayRun = $null
$isolationStatus = $null
$repositoryHash = $null

function Get-Sha256 {
    param([Parameter(Mandatory = $true)][string]$Value)
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Value)
    $digest = [System.Security.Cryptography.SHA256]::HashData($bytes)
    return ([Convert]::ToHexString($digest)).ToLowerInvariant()
}

function Get-RunProvenanceDigest {
    param([Parameter(Mandatory = $true)][object]$Run)
    $cursorBefore = if ($null -eq $Run.cursorBeforeDigest) { "" } else { [string]$Run.cursorBeforeDigest }
    $cursorAfter = if ($null -eq $Run.cursorAfterDigest) { "" } else { [string]$Run.cursorAfterDigest }
    $startedAt = ([DateTimeOffset]::Parse([string]$Run.startedAt)).DateTime.ToString("yyyy-MM-ddTHH:mm:ss.ffffffZ")
    $terminalAt = ([DateTimeOffset]::Parse([string]$Run.terminalAt)).DateTime.ToString("yyyy-MM-ddTHH:mm:ss.ffffffZ")
    return Get-Sha256 "$($Run.state)|$($Run.eventCount)|$([string]$Run.runDigest)|$cursorBefore|$cursorAfter|$startedAt|$terminalAt"
}

function ConvertTo-SnapshotArtifact {
    param([Parameter(Mandatory = $true)][object]$Snapshot)
    return [pscustomobject]@{
        observedAt = $Snapshot.observedAt
        issueCount = $Snapshot.issueCount
        commentCount = $Snapshot.commentCount
        providerCommentCount = $Snapshot.providerCommentCount
        excludedPullRequestCommentCount = $Snapshot.excludedPullRequestCommentCount
        pullRequestCount = $Snapshot.pullRequestCount
        expectedEventCount = $Snapshot.expectedEventCount
        recordCount = $Snapshot.recordCount
        recordDigest = $Snapshot.recordDigest
        snapshotDigest = $Snapshot.snapshotDigest
    }
}

function Get-SetDigest {
    param([object[]]$Values)
    $serialized = @($Values | Sort-Object) -join "`n"
    if ([string]::IsNullOrEmpty($serialized)) { $serialized = "<empty-set>" }
    return Get-Sha256 $serialized
}

function Get-ProjectContinuityState {
    $candidateResponse = Invoke-Projecta -Method Get -Uri "$($ApiBaseUrl.TrimEnd('/'))/v1/projects/$([uri]::EscapeDataString($ProjectHandle))/candidates?status=all&limit=100"
    $candidateItems = @($candidateResponse.candidates)
    $graphResponse = Invoke-Projecta -Method Get -Uri "$($ApiBaseUrl.TrimEnd('/'))/v1/projects/$([uri]::EscapeDataString($ProjectHandle))/graph?evidence=with-evidence&nodeLimit=100"
    $graphNodes = @($graphResponse.nodes)
    $candidateGraphNodes = @($graphNodes | Where-Object { $_.verificationState -eq "candidate" -and $_.projectScope -eq "selected" })
    $evidenceNodes = @($graphNodes | Where-Object { $_.provenanceState -eq "source-backed" -and $_.projectScope -eq "selected" })
    $candidateHandles = @($candidateItems | ForEach-Object { [string]$_.handle } | Where-Object { $_ } | Sort-Object)
    $candidateGraphHandles = @($candidateGraphNodes | ForEach-Object { [string]$_.handle } | Where-Object { $_ } | Sort-Object)
    $evidenceHandles = @($evidenceNodes | ForEach-Object { [string]$_.handle } | Where-Object { $_ } | Sort-Object)
    return [pscustomobject]@{
        candidateCount = $candidateItems.Count
        candidateProjectScopedCount = $candidateGraphNodes.Count
        evidenceNodeCount = $evidenceNodes.Count
        candidateSourceRevision = [string]$candidateResponse.sourceRevision
        candidateHandles = $candidateHandles
        candidateGraphHandles = $candidateGraphHandles
        evidenceHandles = $evidenceHandles
    }
}

function Get-ContinuityEvidence {
    param(
        [Parameter(Mandatory = $true)][object]$Before,
        [Parameter(Mandatory = $true)][object]$After,
        [Parameter(Mandatory = $true)][int]$RunEventCount
    )
    $candidateAdded = @($After.candidateHandles | Where-Object { $Before.candidateHandles -notcontains $_ })
    $candidateGraphAdded = @($After.candidateGraphHandles | Where-Object { $Before.candidateGraphHandles -notcontains $_ })
    $evidenceAdded = @($After.evidenceHandles | Where-Object { $Before.evidenceHandles -notcontains $_ })
    $candidateRemoved = @($Before.candidateHandles | Where-Object { $After.candidateHandles -notcontains $_ })
    $candidateGraphRemoved = @($Before.candidateGraphHandles | Where-Object { $After.candidateGraphHandles -notcontains $_ })
    $evidenceRemoved = @($Before.evidenceHandles | Where-Object { $After.evidenceHandles -notcontains $_ })
    return [pscustomobject]@{
        preRunCandidateCount = $Before.candidateCount
        postRunCandidateCount = $After.candidateCount
        candidateDeltaCount = $candidateAdded.Count
        candidateRemovedCount = $candidateRemoved.Count
        preRunCandidateSetDigest = Get-SetDigest $Before.candidateHandles
        postRunCandidateSetDigest = Get-SetDigest $After.candidateHandles
        candidateDeltaDigest = Get-SetDigest $candidateAdded
        preRunCandidateGraphCount = $Before.candidateProjectScopedCount
        postRunCandidateGraphCount = $After.candidateProjectScopedCount
        candidateGraphDeltaCount = $candidateGraphAdded.Count
        candidateGraphRemovedCount = $candidateGraphRemoved.Count
        preRunCandidateGraphSetDigest = Get-SetDigest $Before.candidateGraphHandles
        postRunCandidateGraphSetDigest = Get-SetDigest $After.candidateGraphHandles
        candidateGraphDeltaDigest = Get-SetDigest $candidateGraphAdded
        preRunEvidenceNodeCount = $Before.evidenceNodeCount
        postRunEvidenceNodeCount = $After.evidenceNodeCount
        evidenceNodeDeltaCount = $evidenceAdded.Count
        evidenceNodeRemovedCount = $evidenceRemoved.Count
        preRunEvidenceSetDigest = Get-SetDigest $Before.evidenceHandles
        postRunEvidenceSetDigest = Get-SetDigest $After.evidenceHandles
        evidenceDeltaDigest = Get-SetDigest $evidenceAdded
        preRunSourceRevisionDigest = Get-Sha256 $Before.candidateSourceRevision
        postRunSourceRevisionDigest = Get-Sha256 $After.candidateSourceRevision
        runEventCount = $RunEventCount
    }
}

function Add-Step {
    param([Parameter(Mandatory = $true)][string]$Name, [hashtable]$Values = @{})
    $record = [ordered]@{ name = $Name; at = [DateTime]::UtcNow.ToString("o") }
    foreach ($key in $Values.Keys) { $record[$key] = $Values[$key] }
    $steps.Add([pscustomobject]$record)
}

function Invoke-Projecta {
    param(
        [Parameter(Mandatory = $true)][ValidateSet("Get", "Post")][string]$Method,
        [Parameter(Mandatory = $true)][string]$Uri,
        [object]$Body = $null,
        [string]$IdempotencyKey
    )
    $headers = @{
        Accept = "application/json"
        "X-Projecta-Project-Id" = $ProjectId
        "X-Projecta-Actor-Id" = $ActorId
        "X-Projecta-Context-Secret" = $ContextSecret
        "X-Projecta-Selection-Handle" = $ProjectHandle
        "X-Request-Id" = "s11-a18-$([guid]::NewGuid().ToString('N'))"
    }
    if (-not [string]::IsNullOrWhiteSpace($IdempotencyKey)) { $headers["Idempotency-Key"] = $IdempotencyKey }
    # Deliberately no Authorization header and no provider token input.
    if ($Method -eq "Get") { return Invoke-RestMethod -Method Get -Uri $Uri -Headers $headers }
    return Invoke-RestMethod -Method Post -Uri $Uri -Headers $headers -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 8)
}

function Invoke-GitHubCollection {
    param([Parameter(Mandatory = $true)][string]$Path)
    $headers = @{
        Accept = "application/vnd.github+json"
        "User-Agent" = "Projecta-S11-A18"
        "X-GitHub-Api-Version" = "2026-03-10"
    }
    $items = [System.Collections.Generic.List[object]]::new()
    $visited = [System.Collections.Generic.HashSet[string]]::new()
    $totalBytes = 0
    for ($page = 1; $page -le 10; $page++) {
        $uri = "https://api.github.com/repos/$Owner/$Repository/$Path&per_page=100&page=$page"
        if (-not $visited.Add($uri)) { throw "GitHub snapshot pagination cycle detected." }
        $response = Invoke-WebRequest -UseBasicParsing -MaximumRedirection 0 -Uri $uri -Headers $headers
        if ($response.StatusCode -ne 200) { throw "GitHub snapshot returned a bounded non-success status." }
        $totalBytes += [System.Text.Encoding]::UTF8.GetByteCount([string]$response.Content)
        if ($totalBytes -gt 10MB) { throw "GitHub snapshot exceeded the live evidence byte budget." }
        $pageItems = @($response.Content | ConvertFrom-Json)
        foreach ($item in $pageItems) { $items.Add($item) }
        if ($pageItems.Count -lt 100) { return @($items) }
    }
    throw "GitHub snapshot exceeded the bounded page budget."
}

function Get-GitHubSnapshot {
    $issues = @(Invoke-GitHubCollection -Path "issues?state=all&sort=updated&direction=asc")
    $comments = @(Invoke-GitHubCollection -Path "issues/comments?sort=updated&direction=asc")
    $pullRequests = @($issues | Where-Object { $null -ne $_.pull_request })
    $realIssues = @($issues | Where-Object { $null -eq $_.pull_request })
    $pullRequestNumbers = @($pullRequests | ForEach-Object { [string]$_.number })
    $realComments = @($comments | Where-Object {
        $issueUrl = [string]$_.issue_url
        $issueUrl -match '/issues/(?<number>\d+)$' -and $pullRequestNumbers -notcontains [string]$Matches.number
    })
    $recordFingerprints = [System.Collections.Generic.List[string]]::new()
    foreach ($item in $realIssues) {
        $providerId = [string]$item.id
        $updatedAt = [string]$item.updated_at
        if (-not $providerId -or -not $updatedAt) { throw "GitHub issue snapshot record lacks opaque identity or updated_at." }
        $contentDigest = Get-Sha256 "$([string]$item.title)`n$([string]$item.body)"
        $recordFingerprints.Add("issue|$(Get-Sha256 "$Owner/$Repository|issue|$providerId")|$updatedAt|$contentDigest")
    }
    foreach ($item in $realComments) {
        $providerId = [string]$item.id
        $updatedAt = [string]$item.updated_at
        if (-not $providerId -or -not $updatedAt) { throw "GitHub comment snapshot record lacks opaque identity or updated_at." }
        $contentDigest = Get-Sha256 ([string]$item.body)
        $recordFingerprints.Add("issue-comment|$(Get-Sha256 "$Owner/$Repository|issue-comment|$providerId")|$updatedAt|$contentDigest")
    }
    $recordDigest = Get-Sha256 ((@($recordFingerprints | Sort-Object) -join "`n"))
    $snapshotDigest = Get-Sha256 "$recordDigest|$($realIssues.Count)|$($realComments.Count)|$($comments.Count)|$($pullRequests.Count)|$($comments.Count - $realComments.Count)"
    return [pscustomobject]@{
        observedAt = [DateTime]::UtcNow.ToString("o")
        issueCount = $realIssues.Count
        commentCount = $realComments.Count
        providerCommentCount = $comments.Count
        excludedPullRequestCommentCount = $comments.Count - $realComments.Count
        pullRequestCount = $pullRequests.Count
        expectedEventCount = $realIssues.Count + $realComments.Count
        recordCount = $recordFingerprints.Count
        recordDigest = $recordDigest
        snapshotDigest = $snapshotDigest
    }
}

try {
    if ([string]::IsNullOrWhiteSpace($ApiBaseUrl) -or [string]::IsNullOrWhiteSpace($ProjectHandle) -or
        [string]::IsNullOrWhiteSpace($Owner) -or [string]::IsNullOrWhiteSpace($Repository) -or
        [string]::IsNullOrWhiteSpace($SetupHandle) -or [string]::IsNullOrWhiteSpace($ProjectId) -or
        [string]::IsNullOrWhiteSpace($ActorId) -or [string]::IsNullOrWhiteSpace($ContextSecret)) {
        throw "S11-A18 requires API URL, opaque project/setup handles, bounded repository inputs, and trusted Projecta context; no provider credential argument is accepted."
    }
    if ($Owner -notmatch '^[A-Za-z0-9][A-Za-z0-9-]{0,38}$' -or $Repository -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$') {
        throw "The owner and repository inputs are not bounded GitHub path segments."
    }
    $base = "$($ApiBaseUrl.TrimEnd('/'))/v1/projects/$([uri]::EscapeDataString($ProjectHandle))/connectors/installations"
    $repositoryHash = Get-Sha256 "$Owner/$Repository"
    Add-Step "input-validated" @{ repositoryHash = $repositoryHash; credentialProvided = $false }
    $snapshot = Get-GitHubSnapshot
    Add-Step "provider-snapshot" @{ issueCount = $snapshot.issueCount; commentCount = $snapshot.commentCount; providerCommentCount = $snapshot.providerCommentCount; excludedPullRequestCommentCount = $snapshot.excludedPullRequestCommentCount; pullRequestCount = $snapshot.pullRequestCount; expectedEventCount = $snapshot.expectedEventCount; snapshotDigest = $snapshot.snapshotDigest }

    $catalog = Invoke-Projecta -Method Get -Uri "$($ApiBaseUrl.TrimEnd('/'))/v1/projects?limit=100"
    if (@($catalog.projects | Where-Object { $_.handle -eq $ProjectHandle }).Count -ne 1) { throw "The supplied project handle is not in the server-owned catalog." }
    Invoke-Projecta -Method Post -Uri "$($ApiBaseUrl.TrimEnd('/'))/v1/projects/selection" -Body @{ handle = $ProjectHandle; catalogRevision = $catalog.catalogRevision } | Out-Null
    Add-Step "project-selected" @{ catalogRevision = $catalog.catalogRevision; selectionEstablished = $true }

    $installation = Invoke-Projecta -Method Post -Uri $base -IdempotencyKey "s11-a18-create-$([guid]::NewGuid().ToString('N'))" -Body @{ connectorType = "github-public-issues"; githubSetupHandle = $SetupHandle; capabilities = @("inbound-import") }
    Add-Step "create" @{ setupStatus = $installation.setupStatus; revision = $installation.revision; installationDigest = Get-Sha256 ("$($installation.handle)|$($installation.revision)") }
    $enabledInstallation = Invoke-Projecta -Method Post -Uri "$base/$($installation.handle)/enable" -Body @{ expectedInstallationRevision = $installation.revision }
    $enabled = [bool]$enabledInstallation.enabled
    Add-Step "enable" @{ enabled = $enabled; revision = $enabledInstallation.revision }

    $continuityBefore = Get-ProjectContinuityState
    $baselineKey = "s11-a18-baseline-$([guid]::NewGuid().ToString('N'))"
    $baselineRun = Invoke-Projecta -Method Post -Uri "$base/$($installation.handle)/runs" -IdempotencyKey $baselineKey -Body @{ expectedInstallationRevision = $enabledInstallation.revision }
    Add-Step "run" @{ state = $baselineRun.state; eventCount = $baselineRun.eventCount; replayCount = $baselineRun.replayCount; failureCode = $baselineRun.failureCode; runDigest = Get-Sha256 ([string]$baselineRun.handle); cursorBeforeDigest = $baselineRun.cursorBeforeDigest; cursorAfterDigest = $baselineRun.cursorAfterDigest }
    if ($baselineRun.state -ne "succeeded" -or [int]$baselineRun.eventCount -le 0 -or [int]$baselineRun.eventCount -ne [int]$snapshot.expectedEventCount) { throw "The first live run did not import exactly the provider snapshot event count." }
    if ([string]::IsNullOrWhiteSpace($baselineRun.cursorAfterDigest)) { throw "The successful live run did not commit a cursor digest." }

    $continuityAfter = Get-ProjectContinuityState
    $continuity = Get-ContinuityEvidence $continuityBefore $continuityAfter ([int]$baselineRun.eventCount)
    Add-Step "evidence-candidate-continuity" @{ candidateDeltaCount = $continuity.candidateDeltaCount; candidateGraphDeltaCount = $continuity.candidateGraphDeltaCount; evidenceNodeDeltaCount = $continuity.evidenceNodeDeltaCount; candidateSourceRevisionDigest = $continuity.postRunSourceRevisionDigest }
    if ($continuity.candidateDeltaCount -ne [int]$snapshot.expectedEventCount -or $continuity.candidateGraphDeltaCount -ne [int]$snapshot.expectedEventCount -or $continuity.evidenceNodeDeltaCount -lt [int]$snapshot.expectedEventCount -or $continuity.candidateRemovedCount -ne 0 -or $continuity.candidateGraphRemovedCount -ne 0 -or $continuity.evidenceNodeRemovedCount -ne 0) { throw "The live run did not produce an exact project-scoped candidate/evidence delta." }

    $replayRun = Invoke-Projecta -Method Post -Uri "$base/$($installation.handle)/runs" -IdempotencyKey $baselineKey -Body @{ expectedInstallationRevision = $enabledInstallation.revision }
    Add-Step "replay" @{ state = $replayRun.state; eventCount = $replayRun.eventCount; replayCount = $replayRun.replayCount; runDigest = Get-Sha256 ([string]$replayRun.handle) }
    if ($replayRun.state -ne "replayed") { throw "The exact live run replay did not return replayed." }

    try { Invoke-Projecta -Method Get -Uri "$($ApiBaseUrl.TrimEnd('/'))/v1/projects/project-h-forged/connectors/installations" | Out-Null } catch {
        $problem = [string]$_.ErrorDetails.Message
        if ($_.Exception.Message -match "404" -or $problem -match '"status"\s*:\s*404|CONNECTOR_NOT_FOUND') { $isolationStatus = 404 }
    }
    Add-Step "project-isolation" @{ forgedProjectStatus = $isolationStatus }
    if ($isolationStatus -ne 404) { throw "Forged project scope did not fail closed with HTTP 404." }
    $status = "passed"
} catch {
    $failure = "live acceptance assertion failed safely"
} finally {
    if ($null -ne $installation -and $enabled) {
        try {
            $disabled = Invoke-Projecta -Method Post -Uri "$base/$($installation.handle)/disable" -Body @{ expectedInstallationRevision = $enabledInstallation.revision }
            Add-Step "disable" @{ enabled = [bool]$disabled.enabled; revision = $disabled.revision }
        } catch {
            Add-Step "disable" @{ enabled = $null; cleanup = "failed-safely" }
            if ($status -eq "passed") { $status = "failed"; $failure = "live acceptance cleanup failed safely" }
        }
    }
    New-Item -ItemType Directory -Path (Split-Path -Parent $evidence) -Force | Out-Null
    New-Item -ItemType Directory -Path (Split-Path -Parent $journeyEvidence) -Force | Out-Null
    $common = [ordered]@{
        schemaVersion = "sprint11.github-public-issues-live.v2"
        status = $status
        generatedBy = "scripts/run_sprint11_github_public_issues_acceptance.ps1"
        startedAt = $startedAt.ToString("o")
        finishedAt = [DateTime]::UtcNow.ToString("o")
        failure = $failure
        repositoryHash = $repositoryHash
        credentialsPersisted = $false
        rawProviderPayload = $false
        projectHandlePersisted = $false
        providerSnapshot = if ($null -ne $snapshot) { ConvertTo-SnapshotArtifact $snapshot } else { $null }
        installationDigest = if ($null -ne $installation) { Get-Sha256 ("$($installation.handle)|$($installation.revision)") } else { $null }
        baselineRun = if ($null -ne $baselineRun) { $runDigest = Get-Sha256 ([string]$baselineRun.handle); $run = [pscustomobject]@{ state = $baselineRun.state; eventCount = $baselineRun.eventCount; runDigest = $runDigest; cursorBeforeDigest = $baselineRun.cursorBeforeDigest; cursorAfterDigest = $baselineRun.cursorAfterDigest; startedAt = $baselineRun.startedAt; terminalAt = $baselineRun.terminalAt }; Add-Member -InputObject $run -NotePropertyName provenanceDigest -NotePropertyValue (Get-RunProvenanceDigest $run); $run } else { $null }
        replayRun = if ($null -ne $replayRun) { $runDigest = Get-Sha256 ([string]$replayRun.handle); $run = [pscustomobject]@{ state = $replayRun.state; eventCount = $replayRun.eventCount; runDigest = $runDigest; cursorBeforeDigest = $replayRun.cursorBeforeDigest; cursorAfterDigest = $replayRun.cursorAfterDigest; startedAt = $replayRun.startedAt; terminalAt = $replayRun.terminalAt; replayOfRunDigest = if ($null -ne $baselineRun) { Get-Sha256 ([string]$baselineRun.handle) } else { $null }; replayOfEventCount = if ($null -ne $baselineRun) { $baselineRun.eventCount } else { $null }; replayOfCursorBeforeDigest = if ($null -ne $baselineRun) { $baselineRun.cursorBeforeDigest } else { $null }; replayOfCursorAfterDigest = if ($null -ne $baselineRun) { $baselineRun.cursorAfterDigest } else { $null } }; Add-Member -InputObject $run -NotePropertyName provenanceDigest -NotePropertyValue (Get-RunProvenanceDigest $run); $run } else { $null }
        continuity = $continuity
        pullRequestExclusion = if ($null -ne $snapshot -and $null -ne $baselineRun) { [pscustomobject]@{ providerIssueCount = $snapshot.issueCount; providerCommentCount = $snapshot.providerCommentCount; excludedPullRequestCommentCount = $snapshot.excludedPullRequestCommentCount; providerPullRequestCount = $snapshot.pullRequestCount; importedEventCount = $baselineRun.eventCount } } else { $null }
        projectIsolation = [pscustomobject]@{ forgedProjectStatus = $isolationStatus }
    }
    $common.steps = @($steps)
    [pscustomobject]$common | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $evidence -Encoding utf8
    $common.Remove("steps")
    $common.schemaVersion = "sprint11.github-public-issues-live-journey.v2"
    [pscustomobject]$common | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $journeyEvidence -Encoding utf8
}
if ($status -ne "passed") { exit 1 }
