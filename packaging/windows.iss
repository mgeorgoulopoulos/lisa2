#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#ifndef SourceRevision
  #define SourceRevision "local"
#endif
[Setup]
AppId={{9E237F64-2B93-4461-9059-93C1B70D76F5}
AppName=Lisa2
AppVersion={#AppVersion}
AppVerName=Lisa2 {#AppVersion} ({#SourceRevision})
AppPublisher=Michael Georgoulopoulos
DefaultDirName={localappdata}\Programs\Lisa2
DefaultGroupName=Lisa2
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\release
OutputBaseFilename=Lisa2-Windows-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\LICENSE
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\Lisa2.exe
CloseApplications=yes

[Files]
Source: "..\dist\Lisa2\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Lisa2"; Filename: "{app}\Lisa2.exe"
Name: "{group}\Uninstall Lisa2"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\Lisa2.exe"; Description: "Open Lisa2"; Flags: nowait postinstall skipifsilent
