' 糍粑 QQ 机器人 - 后台静默启动（不显示黑窗口）
' 关闭方式：任务管理器结束 python.exe，或双击“4.停止后台.vbs”
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = folder

If Not fso.FileExists(folder & "\.venv\Scripts\pythonw.exe") Then
    MsgBox "尚未安装依赖，请先运行 1.首次安装.bat", 48, "糍粑机器人"
    WScript.Quit
End If
If Not fso.FileExists(folder & "\config.yaml") Then
    MsgBox "未找到 config.yaml，请先运行 1.首次安装.bat 并填写配置", 48, "糍粑机器人"
    WScript.Quit
End If

' pythonw 无窗口运行，日志写入 logs/bot.log
WshShell.Run """" & folder & "\.venv\Scripts\pythonw.exe"" """ & folder & "\main.py""", 0, False
