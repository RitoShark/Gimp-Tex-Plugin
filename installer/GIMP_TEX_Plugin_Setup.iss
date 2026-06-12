; Inno Setup Script for GIMP TEX Plugin
; Detects and installs for GIMP 2.x and/or GIMP 3.x automatically

[Setup]
AppName=GIMP TEX Plugin
AppVersion=2.0
AppPublisher=LtMAO Team
DefaultDirName={autopf}\GIMP_TEX_Plugin
DefaultGroupName=GIMP TEX Plugin
OutputDir=.
OutputBaseFilename=GIMP_TEX_Plugin_Setup
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

[Files]
; ---- GIMP 2.x ----
; Main script in plug-ins/ root (GIMP 2.x scans flat .py files)
Source: "..\gimp2\gimp2_tex_plugin.py"; DestDir: "{code:GetGIMP2PluginDir}"; Flags: ignoreversion; Check: GIMP2Found
; Shared libs in subfolder (plugin adds this to sys.path)
Source: "..\shared\tex_core.py"; DestDir: "{code:GetGIMP2PluginDir}\gimp2_tex_libs"; Flags: ignoreversion; Check: GIMP2Found
Source: "..\shared\dxt_compress.py"; DestDir: "{code:GetGIMP2PluginDir}\gimp2_tex_libs"; Flags: ignoreversion; Check: GIMP2Found
Source: "..\shared\libdxtcompress.dll"; DestDir: "{code:GetGIMP2PluginDir}\gimp2_tex_libs"; Flags: ignoreversion; Check: GIMP2Found
; Optional GPU BC7 accelerator (DirectXTex). Plugin falls back to CPU bc7enc if absent.
Source: "..\shared\Bc7Native.dll"; DestDir: "{code:GetGIMP2PluginDir}\gimp2_tex_libs"; Flags: ignoreversion skipifsourcedoesntexist; Check: GIMP2Found

; ---- GIMP 3.x ----
; All files in named subfolder (GIMP 3.x requirement)
Source: "..\gimp3\gimp3_tex_plugin.py"; DestDir: "{code:GetGIMP3PluginDir}\gimp3_tex_plugin"; Flags: ignoreversion; Check: GIMP3Found
Source: "..\shared\tex_core.py"; DestDir: "{code:GetGIMP3PluginDir}\gimp3_tex_plugin"; Flags: ignoreversion; Check: GIMP3Found
Source: "..\shared\dxt_compress.py"; DestDir: "{code:GetGIMP3PluginDir}\gimp3_tex_plugin"; Flags: ignoreversion; Check: GIMP3Found
Source: "..\shared\libdxtcompress.dll"; DestDir: "{code:GetGIMP3PluginDir}\gimp3_tex_plugin"; Flags: ignoreversion; Check: GIMP3Found
; Optional GPU BC7 accelerator (DirectXTex). Plugin falls back to CPU bc7enc if absent.
Source: "..\shared\Bc7Native.dll"; DestDir: "{code:GetGIMP3PluginDir}\gimp3_tex_plugin"; Flags: ignoreversion skipifsourcedoesntexist; Check: GIMP3Found

[InstallDelete]
; Remove stale compiled bytecode + the old pre-bc7enc DLL so a fresh install
; can't load outdated cached modules (GIMP 2.x uses Python 2.7 .pyc next to .py).
Type: files; Name: "{code:GetGIMP2PluginDir}\gimp2_tex_libs\tex_core.pyc"; Check: GIMP2Found
Type: files; Name: "{code:GetGIMP2PluginDir}\gimp2_tex_libs\dxt_compress.pyc"; Check: GIMP2Found
Type: files; Name: "{code:GetGIMP2PluginDir}\gimp2_tex_libs\dxt_compress.dll"; Check: GIMP2Found

[Code]
var
  GIMP2Dir: String;
  GIMP3Dir: String;
  GIMP2Detected: Boolean;
  GIMP3Detected: Boolean;
  GIMP2Version: String;
  GIMP3Version: String;

function ScanForGIMP2(BasePath: String): Boolean;
var
  FindRec: TFindRec;
  SearchPath: String;
  VersionDir: String;
begin
  Result := False;
  SearchPath := BasePath + '\GIMP';

  // Scan for any 2.x directory (2.8, 2.10, 2.99, etc.)
  if FindFirst(SearchPath + '\*', FindRec) then
  begin
    try
      repeat
        if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
        begin
          VersionDir := FindRec.Name;
          if (Length(VersionDir) >= 3) and (VersionDir[1] = '2') and (VersionDir[2] = '.') then
          begin
            if DirExists(SearchPath + '\' + VersionDir + '\plug-ins') then
            begin
              if (not Result) or (VersionDir > GIMP2Version) then
              begin
                GIMP2Dir := SearchPath + '\' + VersionDir + '\plug-ins';
                GIMP2Version := VersionDir;
                Result := True;
              end;
            end;
          end;
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

function ScanForGIMP3(BasePath: String): Boolean;
var
  FindRec: TFindRec;
  SearchPath: String;
  VersionDir: String;
begin
  Result := False;
  SearchPath := BasePath + '\GIMP';

  // Scan for any 3.x directory (3.0, 3.2, 3.4, etc.)
  if FindFirst(SearchPath + '\*', FindRec) then
  begin
    try
      repeat
        if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
        begin
          VersionDir := FindRec.Name;
          if (Length(VersionDir) >= 3) and (VersionDir[1] = '3') and (VersionDir[2] = '.') then
          begin
            if DirExists(SearchPath + '\' + VersionDir + '\plug-ins') then
            begin
              if (not Result) or (VersionDir > GIMP3Version) then
              begin
                GIMP3Dir := SearchPath + '\' + VersionDir + '\plug-ins';
                GIMP3Version := VersionDir;
                Result := True;
              end;
            end;
          end;
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

function InitializeSetup(): Boolean;
var
  AppData: String;
  LocalAppData: String;
begin
  AppData := ExpandConstant('{userappdata}');
  LocalAppData := ExpandConstant('{localappdata}');

  GIMP2Detected := False;
  GIMP3Detected := False;
  GIMP2Version := '';
  GIMP3Version := '';

  // Scan for GIMP 2.x (any version)
  if ScanForGIMP2(AppData) then
    GIMP2Detected := True
  else if ScanForGIMP2(LocalAppData) then
    GIMP2Detected := True;

  // Scan for GIMP 3.x (any version)
  if ScanForGIMP3(AppData) then
    GIMP3Detected := True
  else if ScanForGIMP3(LocalAppData) then
    GIMP3Detected := True;

  if (not GIMP2Detected) and (not GIMP3Detected) then
  begin
    MsgBox('No GIMP installation found.' + #13#10 + #13#10 +
           'Searched:' + #13#10 +
           '  ' + AppData + '\GIMP\2.*' + #13#10 +
           '  ' + AppData + '\GIMP\3.*' + #13#10 + #13#10 +
           'Install GIMP first, then run this installer again.', mbError, MB_OK);
    Result := False;
  end
  else
    Result := True;
end;

function GIMP2Found(): Boolean;
begin
  Result := GIMP2Detected;
end;

function GIMP3Found(): Boolean;
begin
  Result := GIMP3Detected;
end;

function GetGIMP2PluginDir(Param: String): String;
begin
  Result := GIMP2Dir;
end;

function GetGIMP3PluginDir(Param: String): String;
begin
  Result := GIMP3Dir;
end;

function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo, MemoTypeInfo, MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: String): String;
var
  Memo: String;
begin
  Memo := '';

  if GIMP2Detected then
  begin
    Memo := Memo + 'GIMP ' + GIMP2Version + ' detected' + NewLine;
    Memo := Memo + Space + 'Plugin: gimp2_tex_plugin.py' + NewLine;
    Memo := Memo + Space + 'Location: ' + GIMP2Dir + NewLine;
    Memo := Memo + NewLine;
  end
  else
    Memo := Memo + 'GIMP 2.x: not found' + NewLine;

  if GIMP3Detected then
  begin
    Memo := Memo + 'GIMP ' + GIMP3Version + ' detected' + NewLine;
    Memo := Memo + Space + 'Plugin: gimp3_tex_plugin.py' + NewLine;
    Memo := Memo + Space + 'Location: ' + GIMP3Dir + '\gimp3_tex_plugin\' + NewLine;
    Memo := Memo + NewLine;
  end
  else
    Memo := Memo + 'GIMP 3.x: not found' + NewLine;

  Memo := Memo + NewLine;
  Memo := Memo + 'Files:' + NewLine;
  Memo := Memo + Space + 'Plugin script (.py)' + NewLine;
  Memo := Memo + Space + 'TEX format library (.py)' + NewLine;
  Memo := Memo + Space + 'DXT compression library (.py + .dll)' + NewLine;

  Result := Memo;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Message: String;
  CachePath: String;
begin
  if CurStep = ssPostInstall then
  begin
    // Clear plugin caches
    if GIMP2Detected then
    begin
      CachePath := ExpandConstant('{userappdata}') + '\GIMP\' + GIMP2Version + '\pluginrc';
      if FileExists(CachePath) then DeleteFile(CachePath);
    end;
    if GIMP3Detected then
    begin
      CachePath := ExpandConstant('{userappdata}') + '\GIMP\' + GIMP3Version + '\pluginrc';
      if FileExists(CachePath) then DeleteFile(CachePath);
    end;

    Message := 'Installation complete.' + #13#10 + #13#10;

    if GIMP2Detected then
      Message := Message + 'GIMP ' + GIMP2Version + ': installed' + #13#10;
    if GIMP3Detected then
      Message := Message + 'GIMP ' + GIMP3Version + ': installed' + #13#10;

    Message := Message + #13#10 +
               'Restart GIMP to activate the plugin.' + #13#10 + #13#10 +
               'Load:    File > Open > .tex file' + #13#10 +
               'Export:  File > Export As > .tex extension';

    MsgBox(Message, mbInformation, MB_OK);
  end;
end;

[Icons]
Name: "{group}\Uninstall GIMP TEX Plugin"; Filename: "{uninstallexe}"

[UninstallDelete]
; GIMP 2.x (covers 2.8, 2.10, etc.)
Type: files; Name: "{userappdata}\GIMP\2.8\plug-ins\gimp2_tex_plugin.py"
Type: filesandordirs; Name: "{userappdata}\GIMP\2.8\plug-ins\gimp2_tex_libs"
Type: files; Name: "{userappdata}\GIMP\2.10\plug-ins\gimp2_tex_plugin.py"
Type: filesandordirs; Name: "{userappdata}\GIMP\2.10\plug-ins\gimp2_tex_libs"
; GIMP 3.x
Type: filesandordirs; Name: "{userappdata}\GIMP\3.0\plug-ins\gimp3_tex_plugin"
Type: filesandordirs; Name: "{userappdata}\GIMP\3.2\plug-ins\gimp3_tex_plugin"
Type: filesandordirs; Name: "{userappdata}\GIMP\3.4\plug-ins\gimp3_tex_plugin"
Type: filesandordirs; Name: "{userappdata}\GIMP\3.6\plug-ins\gimp3_tex_plugin"

[Messages]
WelcomeLabel2=League of Legends .tex texture plugin for GIMP.%n%nSupports GIMP 2.x and 3.x (auto-detected).%n%nLoad and export DXT1, DXT5, and BGRA8 textures with:%n  - Compression format selection%n  - Floyd-Steinberg error diffusion dithering%n  - Perceptual and uniform error metrics%n  - Lanczos3 mipmap generation%n  - Native C compression (fast)
FinishedLabel=Done. Restart GIMP to activate the plugin.
