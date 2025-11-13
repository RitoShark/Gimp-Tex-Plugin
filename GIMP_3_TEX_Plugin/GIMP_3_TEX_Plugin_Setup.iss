; Inno Setup Script for GIMP 3.0 .tex Plugin
; Automatically installs the plugin to GIMP 3.0's plugin directory

[Setup]
AppName=GIMP 3.0 TEX Plugin
AppVersion=3.0
AppPublisher=LtMAO Team
AppPublisherURL=
DefaultDirName={autopf}\GIMP_3_TEX_Plugin
DefaultGroupName=GIMP 3.0 TEX Plugin
OutputDir=.
OutputBaseFilename=GIMP_3_TEX_Plugin_Setup
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
Name: "fastcompression"; Description: "Install Fast DXT Compression DLL (Recommended - 10-100x faster)"; GroupDescription: "Performance:"; Flags: checkablealone
Name: "errorcloser"; Description: "Install Error Dialog Auto-Closer (Recommended)"; GroupDescription: "Additional Features:"; Flags: checkablealone

[Files]
; Install main plugin file (always)
Source: "gimp_tex_plugin_3.py"; DestDir: "{code:GetGIMPPluginDir}\gimp_tex_plugin_3"; Flags: ignoreversion
; Install fast compression DLL (optional)
Source: "dxt_compress.dll"; DestDir: "{code:GetGIMPPluginDir}\gimp_tex_plugin_3"; Flags: ignoreversion; Tasks: fastcompression
Source: "libwinpthread-1.dll"; DestDir: "{code:GetGIMPPluginDir}\gimp_tex_plugin_3"; Flags: ignoreversion; Tasks: fastcompression
Source: "libgomp-1.dll"; DestDir: "{code:GetGIMPPluginDir}\gimp_tex_plugin_3"; Flags: ignoreversion; Tasks: fastcompression
Source: "libgcc_s_seh-1.dll"; DestDir: "{code:GetGIMPPluginDir}\gimp_tex_plugin_3"; Flags: ignoreversion; Tasks: fastcompression
Source: "libstdc++-6.dll"; DestDir: "{code:GetGIMPPluginDir}\gimp_tex_plugin_3"; Flags: ignoreversion; Tasks: fastcompression
; Install error closer (optional, based on checkbox)
Source: "close_gimp_tex_error.py"; DestDir: "{code:GetGIMPPluginDir}\gimp_tex_plugin_3"; Flags: ignoreversion; Tasks: errorcloser; AfterInstall: ShowSuccessMessage

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
  
  // Try to find GIMP 3.0 plugin directory automatically
  AppDataPath := ExpandConstant('{userappdata}');
  LocalAppDataPath := ExpandConstant('{localappdata}');
  
  // Check common GIMP 3.0 locations
  if DirExists(AppDataPath + '\GIMP\3.0\plug-ins') then
  begin
    GIMPPluginDir := AppDataPath + '\GIMP\3.0\plug-ins';
    Result := True;
  end
  else if DirExists(LocalAppDataPath + '\GIMP\3.0\plug-ins') then
  begin
    GIMPPluginDir := LocalAppDataPath + '\GIMP\3.0\plug-ins';
    Result := True;
  end
  else
  begin
    // GIMP 3.0 not found - show error
    MsgBox('GIMP 3.0 plugin directory not found!' + #13#10 + #13#10 +
           'Expected locations:' + #13#10 +
           AppDataPath + '\GIMP\3.0\plug-ins' + #13#10 +
           'or' + #13#10 +
           LocalAppDataPath + '\GIMP\3.0\plug-ins' + #13#10 + #13#10 +
           'Please make sure GIMP 3.0 is installed.' + #13#10 + #13#10 +
           'Note: This installer is for GIMP 3.0 only.' + #13#10 +
           'For GIMP 2.10, use the other installer.', mbError, MB_OK);
    Result := False;
  end;
end;

function GetGIMPPluginDir(Param: String): String;
begin
  Result := GIMPPluginDir;
end;

procedure ShowSuccessMessage();
var
  PluginFile: String;
  CloserFile: String;
  PluginFolder: String;
begin
  PluginFolder := GIMPPluginDir + '\gimp_tex_plugin_3';
  PluginFile := PluginFolder + '\gimp_tex_plugin_3.py';
  CloserFile := PluginFolder + '\close_gimp_tex_error.py';
  
  if FileExists(PluginFile) then
  begin
    InstallationSuccess := True;
    Log('Plugin successfully installed to: ' + PluginFolder);
    if FileExists(CloserFile) then
      Log('Error closer also installed')
    else
      Log('Error closer not installed (user choice)');
  end
  else
  begin
    InstallationSuccess := False;
    MsgBox('Warning: Plugin files may not have been installed correctly.', mbError, MB_OK);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  PluginFolder: String;
  CloserFile: String;
  Message: String;
begin
  if CurStep = ssPostInstall then
  begin
    if InstallationSuccess then
    begin
      PluginFolder := GIMPPluginDir + '\gimp_tex_plugin_3';
      CloserFile := PluginFolder + '\close_gimp_tex_error.py';
      
      Message := 'GIMP 3.0 TEX Plugin installed successfully!' + #13#10 + #13#10 +
                 'Features:' + #13#10 +
                 '  • Load League of Legends .tex files' + #13#10 +
                 '  • Export images as .tex files' + #13#10;
      
      if FileExists(CloserFile) then
        Message := Message + '  • Auto-close error dialogs (installed)' + #13#10
      else
        Message := Message + '  • Error dialog closer (not installed)' + #13#10;
      
      Message := Message + #13#10 +
                 'Please restart GIMP if it''s currently running.' + #13#10 + #13#10 +
                 'Usage:' + #13#10 +
                 '  Load: File > Open > select .tex file' + #13#10 +
                 '  Export: File > Export As > choose .tex extension';
      
      MsgBox(Message, mbInformation, MB_OK);
    end;
  end;
end;

function InitializeUninstall(): Boolean;
var
  AppDataPath: String;
  LocalAppDataPath: String;
  PluginFolder: String;
begin
  // Find plugin folder to uninstall
  AppDataPath := ExpandConstant('{userappdata}');
  LocalAppDataPath := ExpandConstant('{localappdata}');
  
  if DirExists(AppDataPath + '\GIMP\3.0\plug-ins\gimp_tex_plugin_3') then
    PluginFolder := AppDataPath + '\GIMP\3.0\plug-ins\gimp_tex_plugin_3'
  else if DirExists(LocalAppDataPath + '\GIMP\3.0\plug-ins\gimp_tex_plugin_3') then
    PluginFolder := LocalAppDataPath + '\GIMP\3.0\plug-ins\gimp_tex_plugin_3'
  else
    PluginFolder := '';
  
  if PluginFolder <> '' then
  begin
    if DirExists(PluginFolder) then
    begin
      DelTree(PluginFolder, True, True, True);
      Log('Plugin uninstalled from: ' + PluginFolder);
    end;
  end;
  
  Result := True;
end;

[Icons]
Name: "{group}\Uninstall GIMP 3.0 TEX Plugin"; Filename: "{uninstallexe}"

[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\GIMP\3.0\plug-ins\gimp_tex_plugin_3"
Type: filesandordirs; Name: "{localappdata}\GIMP\3.0\plug-ins\gimp_tex_plugin_3"

[Messages]
WelcomeLabel2=This will install the GIMP 3.0 TEX Plugin on your computer.%n%nThis plugin allows you to load and export League of Legends .tex texture files in GIMP 3.0.%n%nFeatures:%n• Load DXT1, DXT5, and BGRA8 textures%n• Export images as TEX files%n• Optional: Auto-close error dialogs
FinishedLabel=GIMP 3.0 TEX Plugin has been installed successfully.%n%nPlease restart GIMP if it's currently running.
SelectTasksLabel2=Select the additional features you want to install:%n%n• Error Dialog Auto-Closer: Automatically closes the annoying "could not open image" error dialog that appears due to a GIMP 3.0 Windows bug. The image actually loads successfully, but GIMP shows an error anyway. This feature closes that dialog automatically.%n%nNote: The error closer works in all languages and runs silently in the background.
