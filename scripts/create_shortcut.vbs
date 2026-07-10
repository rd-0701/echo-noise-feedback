' Create desktop shortcut for Echo
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Get project path
scriptPath = WScript.ScriptFullName
projectPath = fso.GetParentFolderName(fso.GetParentFolderName(scriptPath))

' Desktop path
desktopPath = WshShell.SpecialFolders("Desktop")

' Shortcut path
shortcutName = "Echo Public Access"
shortcutPath = desktopPath & "\" & shortcutName & ".lnk"

' Create shortcut
Set shortcut = WshShell.CreateShortcut(shortcutPath)
shortcut.TargetPath = projectPath & "\scripts\run_tunnel.bat"
shortcut.WorkingDirectory = projectPath & "\scripts"
shortcut.Description = "Echo Noise Feedback - Start with public URL"
shortcut.Save

WScript.Echo "Shortcut created: " & shortcutPath