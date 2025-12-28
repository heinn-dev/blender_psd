Option Explicit

Dim app, args, jsxPath

Set args = WScript.Arguments

If args.Count = 0 Then
    WScript.Quit
End If

jsxPath = args(0)

On Error Resume Next
    Set app = GetObject(, "Photoshop.Application")
    
    If Err.Number = 0 Then
        app.DoJavaScriptFile jsxPath
    End If
On Error GoTo 0