!ifndef PACKAGE_DIR
  !error "PACKAGE_DIR is required"
!endif
!ifndef OUTPUT_FILE
  !error "OUTPUT_FILE is required"
!endif

Unicode true
Name "Projecta 0.7.0 unsigned test pre-release"
OutFile "${OUTPUT_FILE}"
InstallDir "$LOCALAPPDATA\Programs\Projecta\0.7.0"
RequestExecutionLevel user
ShowInstDetails show
ShowUninstDetails show
SetCompressor /SOLID lzma
SetCompressorDictSize 32
CRCCheck on
BrandingText "Projecta 0.7.0 unsigned test pre-release"

!include "MUI2.nsh"
Var StageDir
Var PreviousDir
Var PowerShell
Var HadPrevious
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN "$SYSDIR\WindowsPowerShell\v1.0\powershell.exe"
!define MUI_FINISHPAGE_RUN_PARAMETERS "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File $\"$INSTDIR\ProjectaStart.ps1$\""
!define MUI_FINISHPAGE_RUN_TEXT "Open Projecta"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\Projecta-0.7.0-Unsigned-Pre-Release-Test"

Function .onInit
  IfSilent proceed
  SetShellVarContext current
  MessageBox MB_ICONEXCLAMATION|MB_OKCANCEL|MB_DEFBUTTON2 "Projecta 0.7.0 is an owner-authorized unsigned test pre-release. Windows cannot verify the publisher, and SmartScreen or antivirus software may warn. Continue only if you obtained this installer from the owner-approved source and verified its published SHA-256. Projecta itself installs and runs per-user and is never elevated. If the x64 Visual C++ prerequisite is missing, Internet access is required and setup will ask before downloading the official Microsoft installer directly; Microsoft shows its own license/consent screen and may request approval through Windows UAC. Clean Windows installation, publisher identity, and production readiness are not certified." IDOK proceed
  Abort
proceed:
  SetShellVarContext current
  Return
FunctionEnd

Section "Install Projecta 0.7.0"
  SetShellVarContext current
  StrCpy $PowerShell "$SYSDIR\WindowsPowerShell\v1.0\powershell.exe"
  CreateDirectory "$INSTDIR\.."
  GetTempFileName $0 "$INSTDIR\.."
  Delete "$0"
  StrCpy $StageDir "$0.staging"
  GetTempFileName $0 "$INSTDIR\.."
  Delete "$0"
  StrCpy $PreviousDir "$0.previous"
  CreateDirectory "$StageDir"
  SetOutPath "$StageDir"
  File /r "${PACKAGE_DIR}\*"

  ClearErrors
  ExecWait '"$PowerShell" -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "$StageDir\ProjectaStart.ps1" -InstallOnly' $1
  IfErrors prerequisiteCheckFailed
  StrCmp $1 0 prerequisiteReady prerequisiteCheckFailed

prerequisiteCheckFailed:
  SetOutPath "$INSTDIR\.."
  RMDir /r "$StageDir"
  MessageBox MB_ICONSTOP|MB_OK "Projecta was not installed because its Microsoft Visual C++ prerequisite could not be prepared or verified. Nothing in an existing Projecta installation or workspace was changed. Connect to the Internet, rerun setup, and approve the Microsoft installer through its own license screen and Windows UAC prompt if required. Error code: $1"
  SetErrorLevel 30
  Abort

prerequisiteReady:
  StrCpy $HadPrevious 0
  IfFileExists "$INSTDIR" backupExistingIfDir stageReady

backupExistingIfDir:
  IfFileExists "$INSTDIR\*.*" backupExisting stageReady

backupExisting:
  ClearErrors
  Rename "$INSTDIR" "$PreviousDir"
  IfErrors backupFailed
  StrCpy $HadPrevious 1

stageReady:
  SetOutPath "$INSTDIR\.."
  ClearErrors
  IfFileExists "$INSTDIR" removeEmptyTargetDir commitRename

removeEmptyTargetDir:
  RMDir "$INSTDIR"
  ClearErrors

commitRename:
  Rename "$StageDir" "$INSTDIR"
  IfErrors installCommitFailed
  StrCmp $HadPrevious 1 removePrevious cleanupTempPrevious

cleanupTempPrevious:
  RMDir "$PreviousDir"

removePrevious:
  RMDir /r "$PreviousDir"
  Goto finishCommit

finishCommit:
  SetOutPath "$INSTDIR"
  WriteUninstaller "$INSTDIR\..\uninstall-0.7.0.exe"
  CreateDirectory "$SMPROGRAMS\Projecta"
  CreateShortCut "$SMPROGRAMS\Projecta\Projecta.lnk" "$PowerShell" "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File $\"$INSTDIR\ProjectaStart.ps1$\"" "$INSTDIR\Projecta.exe" 0 SW_SHOWNORMAL "" "Projecta 0.7.0 unsigned test pre-release"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayName" "Projecta 0.7.0 unsigned test pre-release"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayVersion" "0.7.0"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\Projecta.exe"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "UninstallString" "$\"$INSTDIR\..\uninstall-0.7.0.exe$\""
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoRepair" 1
  Goto installComplete

backupFailed:
  SetOutPath "$INSTDIR\.."
  RMDir /r "$StageDir"
  MessageBox MB_ICONSTOP|MB_OK "Projecta could not safely replace the existing installation. The existing application files and workspace were left in place. Close any open Projecta installer or application and retry."
  SetErrorLevel 31
  Abort

installCommitFailed:
  StrCmp $HadPrevious 1 restorePrevious previousInstallPreserved

restorePrevious:
  ClearErrors
  Rename "$PreviousDir" "$INSTDIR"
  IfErrors rollbackFailed previousInstallPreserved

previousInstallPreserved:
  RMDir /r "$StageDir"
  RMDir "$PreviousDir"
  MessageBox MB_ICONSTOP|MB_OK "Projecta could not commit the staged application files. The previous installation was restored or left in place. Your workspace was not changed. Retry setup."
  SetErrorLevel 32
  Abort

rollbackFailed:
  MessageBox MB_ICONSTOP|MB_OK "Projecta could not commit the staged files and could not restore the previous application folder automatically. Your previous application files remain at $PreviousDir; workspace data was not changed. Contact the Projecta owner before retrying."
  SetErrorLevel 33
  Abort

installComplete:
SectionEnd

Section "Uninstall"
  SetShellVarContext current
  Delete "$SMPROGRAMS\Projecta\Projecta.lnk"
  RMDir "$SMPROGRAMS\Projecta"
  DeleteRegKey HKCU "${UNINSTALL_KEY}"
  Delete "$INSTDIR\..\uninstall-0.7.0.exe"
  RMDir /r "$INSTDIR"
  RMDir "$INSTDIR\.."
  MessageBox MB_ICONINFORMATION|MB_OK "Projecta application files and shortcuts were removed. Your mutable workspace, databases, secrets, and evidence under %LOCALAPPDATA%\Projecta were intentionally retained. Back up and review that data before deleting it yourself."
SectionEnd
