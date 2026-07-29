param()

$ErrorActionPreference = 'Stop'
$systemTestProject = "projecta-system-test-$([guid]::NewGuid().ToString('N').Substring(0, 12))"
$composeArgs = @('-p', $systemTestProject, '--profile', 'system-test')

try {
    & docker compose @composeArgs up --build --abort-on-container-exit --exit-code-from semantic-core-system-test semantic-core-system-test
    exit $LASTEXITCODE
}
finally {
    & docker compose @composeArgs down --volumes --remove-orphans
}
