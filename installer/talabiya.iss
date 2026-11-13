; Talabiya (طلبية) 0.1.0 - Windows installer (Inno Setup 6)
;
; Build:  bash build_exe/build.sh        (PyInstaller one-folder build + this script)
; Input:  build_exe\dist\Talabiya\  (Talabiya.exe + _internal\)  -> {app}
; Output: installer\Output\Talabiya_Setup_0.1.0.exe
;
; The user's data (%APPDATA%\Talabiya\talabiya.db) and the backup folder are NEVER removed by
; the uninstaller.
;
; This file is UTF-8 with BOM (Arabic messages).

#define AppName      "Talabiya"
#define AppTitle     "طلبية"
#define AppVersion   "0.1.0"
#define AppExe       "Talabiya.exe"
#define AppUserModel "Talabiya.Talabiya"
#define DistGui      "..\build_exe\dist\Talabiya"

#if !FileExists(AddBackslash(SourcePath) + DistGui + "\" + AppExe)
  #error "Build missing - run: bash build_exe/build.sh"
#endif

[Setup]
AppId={{38849D42-EB73-4ADA-B030-48D0724756DA}
AppName={#AppTitle} - {#AppName}
AppVersion={#AppVersion}
AppVerName={#AppTitle} {#AppVersion}
AppPublisher=Talabiya
UninstallDisplayName={#AppTitle} - {#AppName} {#AppVersion}
UninstallDisplayIcon={app}\{#AppExe}
VersionInfoVersion={#AppVersion}.0
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} {#AppVersion} Setup
; --- per-user install: no administrator rights needed
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppTitle}
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
UsePreviousTasks=yes
CloseApplications=yes
ShowLanguageDialog=no
WizardStyle=modern
SetupIconFile=..\talabiya\gui\assets\talabiya.ico
OutputDir=Output
OutputBaseFilename=Talabiya_Setup_{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes

[Languages]
Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"

[Messages]
arabic.FinishedLabel=اكتمل تثبيت [name] على جهازك.%n%nعند التشغيل الأول يطلب البرنامج إنشاء كلمة سر وسؤال سري لاسترجاعها، ثم مراجعة قائمة الأصناف واختيار مجلد النسخ الاحتياطي.

[CustomMessages]
arabic.AppDescription=مشتريات المطاعم اليومية والعهدة
arabic.DataKept=لم تُحذف بيانات البرنامج ولا النسخ الاحتياطية:%n%n  %1%n  ومجلد النسخ الاحتياطية الذي اخترته.%n%nلا تحذفها إلا إذا كنت متأكداً من عدم الحاجة إليها.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#DistGui}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; files of an older build that the new one no longer contains
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{group}\{#AppTitle}"; Filename: "{app}\{#AppExe}"; AppUserModelID: "{#AppUserModel}"; Comment: "{cm:AppDescription}"
Name: "{group}\{cm:UninstallProgram,{#AppTitle}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppTitle}"; Filename: "{app}\{#AppExe}"; AppUserModelID: "{#AppUserModel}"; Comment: "{cm:AppDescription}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppTitle}}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{userappdata}\Talabiya');
    if DirExists(DataDir) and not UninstallSilent then
      MsgBox(FmtMessage(CustomMessage('DataKept'), [DataDir]), mbInformation, MB_OK);
  end;
end;
