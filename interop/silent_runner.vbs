Option Explicit

Dim app, args, jsxPath

Set args = WScript.Arguments

If args.Count = 0 Then
    WScript.Quit
End If

jsxPath = args(0)

Dim jsxArgs(), i
If args.Count > 1 Then
    ReDim jsxArgs(args.Count - 2)
    For i = 1 To args.Count - 1
        jsxArgs(i - 1) = args(i)
    Next
End If

On Error Resume Next
    Set app = GetObject(, "Photoshop.Application")
    
    If Err.Number = 0 Then
        If args.Count > 1 Then
            app.DoJavaScriptFile jsxPath, jsxArgs
        Else
            app.DoJavaScriptFile jsxPath
        End If
    End If
On Error GoTo 0