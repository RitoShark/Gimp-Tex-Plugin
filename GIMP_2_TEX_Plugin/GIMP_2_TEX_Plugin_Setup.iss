; Inno Setup Script for GIMP 2.10 .tex Plugin
; Automatically installs the plugin to GIMP 2.10's plugin directory

[Setup]
AppName=GIMP 2.10 TEX Plugin
AppVersion=2.0
AppPublisher=LtMAO Team
AppPublisherURL=
DefaultDirName={autopf}\GIMP_2_TEX_Plugin
DefaultGroupName=GIMP 2.10 TEX Plugin
OutputDir=.
OutputBaseFilename=GIMP_2_TEX_Plugin_Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
DisableReadyPage=no
DisableFinishedPage=no
WizardStyle=modern
SetupIconFile=compiler:SetupClassicIcon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "fastcompression"; Description: "Install Fast DXT Compression DLL (Recommended - 10-100x faster)"; GroupDescription: "Performance:"; Flags: checkedonce

[Files]
; Install main plugin file (always)
Source: "gimp_tex_plugin.py"; DestDir: "{code:GetGIMPPluginDir}"; Flags: ignoreversion
; Install fast compression DLL (optional)
Source: "dxt_compress.dll"; DestDir: "{code:GetGIMPPluginDir}"; Flags: ignoreversion; Tasks: fastcompression
Source: "libwinpthread-1.dll"; DestDir: "{code:GetGIMPPluginDir}"; Flags: ignoreversion; Tasks: fastcompression
Source: "libgcc_s_seh-1.dll"; DestDir: "{code:GetGIMPPluginDir}"; Flags: ignoreversion; Tasks: fastcompression; Check: FileExists('libgcc_s_seh-1.dll')
Source: "libstdc++-6.dll"; DestDir: "{code:GetGIMPPluginDir}"; Flags: ignoreversion; Tasks: fastcompression; Check: FileExists('libstdc++-6.dll')

[Code]
var
  GIMPPluginDir: String;
  InstallationSuccess: Boolean;

function InitializeSetup(): Boolean;
var
  AppDataPath: String;
  LocalAppDataPath: String;
begin
  InstallationSuccess := False;
  
  // Try to find GIMP 2.10 plugin directory automatically
  AppDataPath := ExpandConstant('{userappdata}');
  LocalAppDataPath := ExpandConstant('{localappdata}');
  
  // Check common GIMP 2.10 locations
  if DirExists(AppDataPath + '\GIMP\2.10\plug-ins') then
  begin
    GIMPPluginDir := AppDataPath + '\GIMP\2.10\plug-ins';
    Result := True;
  end
  else if DirExists(LocalAppDataPath + '\GIMP\2.10\plug-ins') then
  begin
    GIMPPluginDir := LocalAppDataPath + '\GIMP\2.10\plug-ins';
    Result := True;
  end
  else
  begin
    // GIMP 2.10 not found - show error
    MsgBox('GIMP 2.10 plugin directory not found!' + #13#10 + #13#10 +
           'Expected locations:' + #13#10 +
           AppDataPath + '\GIMP\2.10\plug-ins' + #13#10 +
           'or' + #13#10 +
           LocalAppDataPath + '\GIMP\2.10\plug-ins' + #13#10 + #13#10 +
           'Please make sure GIMP 2.10 is installed.' + #13#10 + #13#10 +
           'Note: This installer is for GIMP 2.10 only.' + #13#10 +
           'For GIMP 3.0, use the GIMP 3.0 installer.', mbError, MB_OK);
    Result := False;
  end;
end;

function GetGIMPPluginDir(Param: String): String;
begin
  Result := GIMPPluginDir;
end;

procedure DeletePluginCache();
var
  CachePath: String;
begin
  CachePath := ExpandConstant('{userappdata}') + '\GIMP\2.10\pluginrc';
  if FileExists(CachePath) then
  begin
    DeleteFile(CachePath);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Delete plugin cache to force GIMP to re-scan plugins
    DeletePluginCache();
    InstallationSuccess := True;
  end;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
end;

procedure ShowSuccessMessage();
begin
  if InstallationSuccess then
  begin
    MsgBox('Installation complete!' + #13#10 + #13#10 +
           'The GIMP 2.10 TEX plugin has been installed.' + #13#10 + #13#10 +
           'Please restart GIMP to use the plugin.' + #13#10 + #13#10 +
           'You can now open and save .tex files directly in GIMP!', 
           mbInformation, MB_OK);
  end;
end;

procedure DeinitializeSetup();
begin
  if InstallationSuccess then
  begin
    ShowSuccessMessage();
  end;
end;
