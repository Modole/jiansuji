; Inno Setup Script for HarmonicTester
#define MyAppName "谐波减速机测试系统"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "YourCompany"
#define MyAppExeName "HarmonicTester.exe"

[Setup]
AppId={{7F62F0AD-40B7-4AC7-A993-2E4B5A0E099A}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\HarmonicTester
DefaultGroupName={#MyAppName}
OutputDir=installer\output
OutputBaseFilename=HarmonicTesterSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
DisableDirPage=no
DisableProgramGroupPage=no
SetupIconFile=assets\app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
; Uncomment these lines after configuring [SignTool] section
; SignTool=mysigntool
; SignedUninstaller=yes

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "其他选项:"; Flags: unchecked

[Files]
; For onedir build, include the whole folder
Source: "dist\HarmonicTester\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动{#MyAppName}"; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKCU; Subkey: "Software\HarmonicTester"; Flags: uninsdeletekey ifempty
Root: HKCU; Subkey: "Software\HarmonicTester"; ValueType: string; ValueName: "InstallDir"; ValueData: "{app}"
Root: HKCU; Subkey: "Software\HarmonicTester"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"

[SignTool]
; Configure code signing (optional):
; mysigntool="signtool sign /fd sha256 /tr http://timestamp.digicert.com /td sha256 /f C:\Path\To\cert.pfx /p yourPfxPassword $f"