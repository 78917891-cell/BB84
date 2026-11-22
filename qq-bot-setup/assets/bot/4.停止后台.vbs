' 停止后台运行的糍粑机器人（只结束运行本目录 main.py 的 python 进程）
Set objWMIService = GetObject("winmgmts:\\.\root\cimv2")
Set colItems = objWMIService.ExecQuery("Select * from Win32_Process Where Name = 'pythonw.exe'")
folder = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
n = 0
For Each objItem In colItems
    If InStr(objItem.CommandLine, "main.py") > 0 And InStr(objItem.CommandLine, folder) > 0 Then
        objItem.Terminate()
        n = n + 1
    End If
Next
If n > 0 Then
    MsgBox "已停止 " & n & " 个机器人进程", 64, "糍粑机器人"
Else
    MsgBox "没有找到正在后台运行的机器人", 64, "糍粑机器人"
End If
