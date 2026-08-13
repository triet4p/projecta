param(
    [string]$ApiBaseUrl = $env:PROJECTA_GITHUB_ACCEPTANCE_API_URL,
    [string]$ProjectHandle = $env:PROJECTA_GITHUB_ACCEPTANCE_PROJECT_HANDLE,
    [string]$Owner = $env:PROJECTA_GITHUB_ACCEPTANCE_OWNER,
    [string]$Repository = $env:PROJECTA_GITHUB_ACCEPTANCE_REPOSITORY,
    [string]$ProjectId = $env:PROJECTA_GITHUB_ACCEPTANCE_PROJECT_ID,
    [string]$ActorId = $env:PROJECTA_GITHUB_ACCEPTANCE_ACTOR_ID,
    [string]$ContextSecret = $env:PROJECTA_GITHUB_ACCEPTANCE_CONTEXT_SECRET,
    [string]$JourneyEvidencePath = "docs/sprint-plans/sprint-11/artifacts/s11-A18-github-live-journey.json",
    [string]$BaselineEvidencePath = "docs/sprint-plans/sprint-11/artifacts/s11-A18-github-live-acceptance.json"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$journeyEvidence = Join-Path $root $JourneyEvidencePath
$baselineEvidence = Join-Path $root $BaselineEvidencePath
$startedAt = [DateTime]::UtcNow
$status = "failed"
$failure = $null
$enabled = $false
$installation = $null
$beforeEditRun = $null
$afterEditRun = $null
$replayRun = $null
$beforeEditSnapshot = $null
$afterEditSnapshot = $null
$isolationStatus = $null

function Get-Sha256 {
    param([Parameter(Mandatory = $true)][string]$Value)
    ([Convert]::ToHexString([System.Security.Cryptography.SHA256]::HashData([System.Text.Encoding]::UTF8.GetBytes($Value)))).ToLowerInvariant()
}

function Get-RunProvenanceDigest {
    param([Parameter(Mandatory = $true)][object]$Run)
    $cursorBefore = if ($null -eq $Run.cursorBeforeDigest) { "" } else { [string]$Run.cursorBeforeDigest }
    $cursorAfter = if ($null -eq $Run.cursorAfterDigest) { "" } else { [string]$Run.cursorAfterDigest }
    $startedAt = ([DateTimeOffset]::Parse([string]$Run.startedAt)).DateTime.ToString("yyyy-MM-ddTHH:mm:ss.ffffffZ")
    $terminalAt = ([DateTimeOffset]::Parse([string]$Run.terminalAt)).DateTime.ToString("yyyy-MM-ddTHH:mm:ss.ffffffZ")
    Get-Sha256 "$($Run.state)|$($Run.eventCount)|$([string]$Run.runDigest)|$cursorBefore|$cursorAfter|$startedAt|$terminalAt"
}

function ConvertTo-RunArtifact {
    param([Parameter(Mandatory = $true)][object]$Run, [object]$ReplayOf = $null)
    $runDigest = Get-Sha256 ([string]$Run.handle)
    $artifact = [ordered]@{
        state = $Run.state
        eventCount = $Run.eventCount
        runDigest = $runDigest
        cursorBeforeDigest = $Run.cursorBeforeDigest
        cursorAfterDigest = $Run.cursorAfterDigest
        startedAt = $Run.startedAt
        terminalAt = $Run.terminalAt
    }
    $provenanceInput = [pscustomobject]$artifact
    $artifact.provenanceDigest = Get-RunProvenanceDigest $provenanceInput
    if ($null -ne $ReplayOf) {
        $artifact.replayOfRunDigest = $ReplayOf.runDigest
        $artifact.replayOfEventCount = $ReplayOf.eventCount
        $artifact.replayOfCursorBeforeDigest = $ReplayOf.cursorBeforeDigest
        $artifact.replayOfCursorAfterDigest = $ReplayOf.cursorAfterDigest
    }
    [pscustomobject]$artifact
}

function ConvertTo-SnapshotArtifact {
    param([Parameter(Mandatory = $true)][object]$Snapshot)
    [pscustomobject]@{
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

function Invoke-Projecta {
    param([ValidateSet("Get", "Post")][string]$Method, [string]$Uri, [object]$Body = $null, [string]$IdempotencyKey)
    $headers = @{
        Accept = "application/json"
        "X-Projecta-Project-Id" = $ProjectId
        "X-Projecta-Actor-Id" = $ActorId
        "X-Projecta-Context-Secret" = $ContextSecret
        "X-Projecta-Selection-Handle" = $ProjectHandle
        "X-Request-Id" = "s11-a18-$([guid]::NewGuid().ToString('N'))"
    }
    if ($IdempotencyKey) { $headers["Idempotency-Key"] = $IdempotencyKey }
    # No provider credential or Authorization header is accepted by this journey.
    if ($Method -eq "Get") { return Invoke-RestMethod -Method Get -Uri $Uri -Headers $headers }
    Invoke-RestMethod -Method Post -Uri $Uri -Headers $headers -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 8)
}

function Invoke-GitHubCollection([string]$Path) {
    $headers = @{ Accept = "application/vnd.github+json"; "User-Agent" = "Projecta-S11-A18"; "X-GitHub-Api-Version" = "2026-03-10" }
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

function Get-Snapshot {
    param([object]$KnownIssue = $null, [object]$KnownComment = $null)
    $issues = [System.Collections.Generic.List[object]]::new()
    foreach ($item in @(Invoke-GitHubCollection "issues?state=all&sort=updated&direction=asc")) { $issues.Add($item) }
    if ($null -ne $KnownIssue -and @($issues | Where-Object { [string]$_.number -eq [string]$KnownIssue.number }).Count -eq 0) { $issues.Add($KnownIssue) }
    $comments = [System.Collections.Generic.List[object]]::new()
    foreach ($item in @(Invoke-GitHubCollection "issues/comments?sort=updated&direction=asc")) { $comments.Add($item) }
    if ($null -ne $KnownComment -and @($comments | Where-Object { [int64]$_.id -eq [int64]$KnownComment.id }).Count -eq 0) { $comments.Add($KnownComment) }
    $prs = @($issues | Where-Object { $null -ne $_.pull_request })
    $realIssues = @($issues | Where-Object { $null -eq $_.pull_request })
    $prNumbers = @($prs | ForEach-Object { [string]$_.number })
    $realComments = @($comments | Where-Object {
        $issueUrl = [string]$_.issue_url
        $issueUrl -match '/issues/(?<number>\d+)$' -and $prNumbers -notcontains [string]$Matches.number
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
    $snapshotDigest = Get-Sha256 "$recordDigest|$($realIssues.Count)|$($realComments.Count)|$($comments.Count)|$($prs.Count)|$($comments.Count - $realComments.Count)"
    [pscustomobject]@{
        observedAt = [DateTime]::UtcNow.ToString("o")
        issueCount = $realIssues.Count
        commentCount = $realComments.Count
        providerCommentCount = $comments.Count
        excludedPullRequestCommentCount = $comments.Count - $realComments.Count
        pullRequestCount = $prs.Count
        expectedEventCount = $realIssues.Count + $realComments.Count
        recordCount = $recordFingerprints.Count
        recordDigest = $recordDigest
        snapshotDigest = $snapshotDigest
    }
}

function Wait-ForProviderVisibility {
    param([Parameter(Mandatory = $true)][object]$KnownIssue, [Parameter(Mandatory = $true)][object]$KnownComment)
    for ($attempt = 1; $attempt -le 12; $attempt++) {
        $visibleIssues = @(Invoke-GitHubCollection "issues?state=all&sort=updated&direction=asc")
        $visibleComments = @(Invoke-GitHubCollection "issues/comments?sort=updated&direction=asc")
        $issueVisible = @($visibleIssues | Where-Object { [string]$_.number -eq [string]$KnownIssue.number -and [string]$_.title -eq [string]$KnownIssue.title }).Count -gt 0
        $commentVisible = @($visibleComments | Where-Object { [string]$_.id -eq [string]$KnownComment.id -and [string]$_.body -eq [string]$KnownComment.body }).Count -gt 0
        if ($issueVisible -and $commentVisible) { return }
        Start-Sleep -Seconds 2
    }
    throw "GitHub provider did not expose the created issue/comment revision within the bounded visibility window."
}

try {
    if ($Owner -notmatch '^[A-Za-z0-9][A-Za-z0-9-]{0,38}$' -or $Repository -notmatch '^projecta-s11-github-acceptance-[A-Za-z0-9-]{8,64}$') { throw "Edit journey is restricted to a disposable Sprint 11 acceptance repository." }
    if (-not $ApiBaseUrl -or -not $ProjectHandle -or -not $ProjectId -or -not $ActorId -or -not $ContextSecret) { throw "API URL, opaque project handle, and trusted Projecta context are required." }
    if (-not (Test-Path -LiteralPath $baselineEvidence)) { throw "Baseline evidence must be produced by the credential-free acceptance runner first." }
    $baseline = Get-Content -LiteralPath $baselineEvidence -Raw | ConvertFrom-Json
    $baselineFinishedAt = $baseline.finishedAt
    if ($baseline.status -ne "passed") { throw "Baseline evidence is not passed." }
    $apiRoot = "$($ApiBaseUrl.TrimEnd('/'))"
    $projectRoot = "$apiRoot/v1/projects/$([uri]::EscapeDataString($ProjectHandle))"
    $items = @(Invoke-Projecta Get "$projectRoot/connectors/installations?limit=100").items | Where-Object { $_.connectorType -eq "github-public-issues" }
    if ($items.Count -ne 1) { throw "Expected exactly one GitHub Public Issues installation." }
    $installation = $items[0]
    $enabledInstallation = Invoke-Projecta Post "$projectRoot/connectors/installations/$($installation.handle)/enable" @{ expectedInstallationRevision = $installation.revision }
    $enabled = [bool]$enabledInstallation.enabled

    $issue = gh api "repos/$Owner/$Repository/issues" -f title="Synthetic edit journey issue" -f body="Fabricated issue created for the edit lifecycle journey." | ConvertFrom-Json
    $comment = gh api "repos/$Owner/$Repository/issues/$($issue.number)/comments" -f body="Fabricated comment created before the edit lifecycle run." | ConvertFrom-Json
    Wait-ForProviderVisibility $issue $comment
    $beforeEditSnapshot = Get-Snapshot $issue $comment
    $runBody = @{ expectedInstallationRevision = $enabledInstallation.revision }
    $beforeEditRun = Invoke-Projecta Post "$projectRoot/connectors/installations/$($installation.handle)/runs" $runBody ("s11-a18-before-edit-$([guid]::NewGuid().ToString('N'))")
    $baselineExpectedEventCount = [int]$baseline.providerSnapshot.expectedEventCount
    if ($beforeEditRun.state -ne "succeeded" -or $beforeEditRun.eventCount -ne 2 -or $beforeEditSnapshot.expectedEventCount -ne ($baselineExpectedEventCount + 2)) { throw "The pre-edit live run did not import exactly the two newly created observations." }
    if ([string]$beforeEditRun.cursorBeforeDigest -ne [string]$baseline.baselineRun.cursorAfterDigest) { throw "The pre-edit cursor does not continue the baseline cursor." }

    $issue = gh api --method PATCH "repos/$Owner/$Repository/issues/$($issue.number)" -f title="Synthetic edit journey issue edited" | ConvertFrom-Json
    $comment = gh api --method PATCH "repos/$Owner/$Repository/issues/comments/$($comment.id)" -f body="Fabricated comment edited after the first lifecycle run." | ConvertFrom-Json
    Wait-ForProviderVisibility $issue $comment
    $afterEditSnapshot = Get-Snapshot $issue $comment
    $editKey = "s11-a18-after-edit-$([guid]::NewGuid().ToString('N'))"
    $afterEditRun = Invoke-Projecta Post "$projectRoot/connectors/installations/$($installation.handle)/runs" $runBody $editKey
    if ($afterEditRun.state -ne "succeeded" -or $afterEditRun.eventCount -ne 2 -or $afterEditSnapshot.expectedEventCount -ne $beforeEditSnapshot.expectedEventCount) { throw "The edited issue/comment did not produce exactly two new events without changing cardinality." }
    if ([string]$afterEditRun.cursorBeforeDigest -ne [string]$beforeEditRun.cursorAfterDigest) { throw "The post-edit cursor does not continue the pre-edit cursor." }
    if ([string]$beforeEditSnapshot.recordDigest -eq [string]$afterEditSnapshot.recordDigest -or [string]$beforeEditSnapshot.snapshotDigest -eq [string]$afterEditSnapshot.snapshotDigest) { throw "The edit journey did not change the sanitized provider record digest." }
    $replayRun = Invoke-Projecta Post "$projectRoot/connectors/installations/$($installation.handle)/runs" $runBody $editKey
    if ($replayRun.state -ne "replayed" -or $replayRun.eventCount -ne $afterEditRun.eventCount -or [string]$replayRun.cursorBeforeDigest -ne [string]$afterEditRun.cursorBeforeDigest -or [string]$replayRun.cursorAfterDigest -ne [string]$afterEditRun.cursorAfterDigest -or (Get-Sha256 ([string]$replayRun.handle)) -ne (Get-Sha256 ([string]$afterEditRun.handle))) { throw "The edited lifecycle run did not replay the exact post-edit provenance." }
    try { Invoke-Projecta Get "$apiRoot/v1/projects/project-h-forged/connectors/installations" | Out-Null } catch {
        $problem = [string]$_.ErrorDetails.Message
        if ($_.Exception.Message -match "404" -or $problem -match '"status"\s*:\s*404|CONNECTOR_NOT_FOUND') { $isolationStatus = 404 }
    }
    if ($isolationStatus -ne 404) { throw "Forged project scope did not fail closed." }
    $status = "passed"
} catch { $failure = "edit lifecycle assertion failed safely" }
finally {
    if ($null -ne $installation -and $enabled) {
        try { Invoke-Projecta Post "$projectRoot/connectors/installations/$($installation.handle)/disable" @{ expectedInstallationRevision = $enabledInstallation.revision } | Out-Null } catch { if ($status -eq "passed") { $status = "failed"; $failure = "edit lifecycle cleanup failed safely" } }
    }
    $baselineRun = if ($null -ne $baseline) { $baseline.baselineRun } else { $null }
    $record = [ordered]@{
        schemaVersion = "sprint11.github-public-issues-live-journey.v2"
        status = $status
        generatedBy = "scripts/run_sprint11_github_public_issues_edit_journey.ps1"
        startedAt = $startedAt.ToString("o")
        finishedAt = [DateTime]::UtcNow.ToString("o")
        failure = $failure
        repositoryHash = if ($null -ne $baseline) { $baseline.repositoryHash } else { $null }
        credentialsPersisted = $false
        rawProviderPayload = $false
        projectHandlePersisted = $false
        providerSnapshot = if ($null -ne $baseline) { $baseline.providerSnapshot } else { $null }
        installationDigest = if ($null -ne $installation) { Get-Sha256 ("$($installation.handle)|$($installation.revision)") } else { $null }
        baselineRun = $baselineRun
        continuity = if ($null -ne $baseline) { $baseline.continuity } else { $null }
        baselineFinishedAt = $baselineFinishedAt
        beforeEditSnapshot = if ($null -ne $beforeEditSnapshot) { ConvertTo-SnapshotArtifact $beforeEditSnapshot } else { $null }
        beforeEditRun = if ($null -ne $beforeEditRun) { ConvertTo-RunArtifact $beforeEditRun } else { $null }
        afterEditSnapshot = if ($null -ne $afterEditSnapshot) { ConvertTo-SnapshotArtifact $afterEditSnapshot } else { $null }
        afterEditRun = if ($null -ne $afterEditRun) { ConvertTo-RunArtifact $afterEditRun } else { $null }
        replayRun = if ($null -ne $replayRun -and $null -ne $afterEditRun) { $afterArtifact = ConvertTo-RunArtifact $afterEditRun; ConvertTo-RunArtifact $replayRun $afterArtifact } else { $null }
        editLifecycle = [pscustomobject]@{ verifiedByRun = ($null -ne $beforeEditRun -and $null -ne $afterEditRun -and $null -ne $replayRun -and $beforeEditRun.state -eq "succeeded" -and $afterEditRun.state -eq "succeeded" -and $replayRun.state -eq "replayed" -and $beforeEditRun.eventCount -eq 2 -and $afterEditRun.eventCount -eq 2 -and $null -ne $beforeEditSnapshot -and $null -ne $afterEditSnapshot -and $beforeEditSnapshot.expectedEventCount -eq $afterEditSnapshot.expectedEventCount -and $beforeEditSnapshot.recordDigest -ne $afterEditSnapshot.recordDigest); baselineExpectedEventCount = if ($null -ne $baseline) { $baseline.providerSnapshot.expectedEventCount } else { $null }; beforeEditExpectedEventCount = if ($null -ne $beforeEditSnapshot) { $beforeEditSnapshot.expectedEventCount } else { $null }; afterEditExpectedEventCount = if ($null -ne $afterEditSnapshot) { $afterEditSnapshot.expectedEventCount } else { $null }; beforeEditEventCount = if ($null -ne $beforeEditRun) { $beforeEditRun.eventCount } else { $null }; afterEditEventCount = if ($null -ne $afterEditRun) { $afterEditRun.eventCount } else { $null }; beforeEditRecordDigest = if ($null -ne $beforeEditSnapshot) { $beforeEditSnapshot.recordDigest } else { $null }; afterEditRecordDigest = if ($null -ne $afterEditSnapshot) { $afterEditSnapshot.recordDigest } else { $null } }
        pullRequestExclusion = if ($null -ne $baseline) { [pscustomobject]@{ providerIssueCount = $baseline.providerSnapshot.issueCount; providerCommentCount = $baseline.providerSnapshot.providerCommentCount; excludedPullRequestCommentCount = $baseline.providerSnapshot.excludedPullRequestCommentCount; providerPullRequestCount = $baseline.providerSnapshot.pullRequestCount; importedEventCount = $baseline.baselineRun.eventCount } } else { $null }
        projectIsolation = [pscustomobject]@{ forgedProjectStatus = $isolationStatus }
    }
    New-Item -ItemType Directory -Path (Split-Path -Parent $journeyEvidence) -Force | Out-Null
    [pscustomobject]$record | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $journeyEvidence -Encoding utf8
}
if ($status -ne "passed") { exit 1 }
