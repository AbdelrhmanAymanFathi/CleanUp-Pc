; CleanUp-Pc installer - Inno Setup 6 script
; Build with: build-installer.bat   (or open this file in the Inno Setup compiler)
; Paths below are relative to this file's folder (installer\).

; ---- Single source of truth for the version (keep version.txt in sync) -----
#define MyAppName      "CleanUp-Pc"
#define MyAppVersion   "1.1.0"
#define MyAppPublisher "CleanUp-Pc"
#define MyAppURL       "https://example.com/cleanup-pc"
#define MyAppExeName   "CleanUp-Pc.exe"

[Setup]
; Stable AppId: never change it, it is what lets a new version upgrade the old one.
AppId={{ED1A3E76-9980-453B-AFDC-B321359B1447}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
VersionInfoVersion={#MyAppVersion}
VersionInfoProductName={#MyAppName}
VersionInfoCompany={#MyAppPublisher}

; Admin install into Program Files (64-bit), Windows 10 / Server 2016 or newer
PrivilegesRequired=admin
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

; Output
OutputDir=Output
OutputBaseFilename=CleanUp-Pc-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

; Notice page shown before installing
InfoBeforeFile=notice.txt

; Close the running app before upgrading / uninstalling
CloseApplications=yes
RestartApplications=no

; Add/Remove Programs
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}

; Optional icon: used only if assets\icon.ico exists
#if FileExists("..\assets\icon.ico")
SetupIconFile=..\assets\icon.ico
#endif

; Code signing (optional): build-installer.bat defines SIGN when SIGNTOOL_CMD is set
#ifdef SIGN
SignTool=mysign
SignedUninstaller=yes
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
; Arabic is only added when the translation file exists in your Inno Setup install.
; To add it: download Arabic.isl from https://jrsoftware.org/files/istrans/ and
; copy it to <Inno Setup folder>\Languages\.
#if FileExists(CompilerPath + "Languages\Arabic.isl")
Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"
#endif

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "readme"; Description: "Install README.md"; GroupDescription: "Documentation:"; Flags: unchecked

[Files]
; The PowerShell scripts are bundled inside the .exe by PyInstaller.
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion; Tasks: readme

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent runascurrentuser

[UninstallRun]
; Fallback: make sure the app is not running while files are removed.
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM {#MyAppExeName}"; Flags: runhidden; RunOnceId: "KillCleanUpPc"

[Code]
// The Speed Up undo data is the only way to revert Speed Up, so it is never
// deleted silently: the user is asked (default No), and silent uninstall keeps it.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{commonappdata}\{#MyAppName}');
    if DirExists(DataDir) and (not UninstallSilent) then
    begin
      if MsgBox('Also delete the Speed Up undo data?' + #13#10 + #13#10 +
                DataDir + #13#10 + #13#10 +
                'If you delete it, "Undo Speed Up" will no longer be possible.',
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(DataDir, True, True, True);
    end;
  end;
end;
