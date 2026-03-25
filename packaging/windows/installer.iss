; Inno Setup script for wabbajack-py Windows installer
; Compile with: iscc installer.iss

[Setup]
AppName=wabbajack-py
AppVersion=0.3.0
AppPublisher=wabbajack-py
DefaultDirName={autopf}\wabbajack-py
DefaultGroupName=wabbajack-py
OutputBaseFilename=wabbajack-py-setup
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\..\frontend\public\favicon.svg
UninstallDisplayIcon={app}\wabbajack-py.exe

[Files]
Source: "..\..\dist\wabbajack-py.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\wabbajack-py"; Filename: "{app}\wabbajack-py.exe"; Parameters: "serve"
Name: "{autodesktop}\wabbajack-py"; Filename: "{app}\wabbajack-py.exe"; Parameters: "serve"

[Registry]
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Services\SharedAccess\Parameters\FirewallPolicy\FirewallRules"; \
  ValueType: string; ValueName: "wabbajack-py"; \
  ValueData: "v2.10|Action=Allow|Active=TRUE|Dir=In|Protocol=6|LPort=6969|App={app}\wabbajack-py.exe|Name=wabbajack-py|"; \
  Flags: uninsdeletevalue

[Run]
Filename: "{app}\wabbajack-py.exe"; Parameters: "serve"; Description: "Launch wabbajack-py"; Flags: postinstall nowait
