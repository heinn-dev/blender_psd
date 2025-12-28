Option Explicit

Dim app, args, jsxPath

Set args = WScript.Arguments

If args.Count = 0 Then
    WScript.Quit
End If

jsxPath = args(0)

On Error Resume Next
    ' Connect to the running Photoshop instance
    Set app = GetObject(, "Photoshop.Application")
    
    ' If Photoshop isn't running, this will fail silently (which is what we want)
    If Err.Number = 0 Then
        ' Execute the script directly through the COM interface
        ' This does NOT trigger an OS-level window activation
        app.DoJavaScriptFile jsxPath
    End If
On Error GoTo 0