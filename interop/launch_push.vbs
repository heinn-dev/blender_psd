Option Explicit

' Like silent_runner.vbs, but writes a failure marker when Photoshop is not
' running. Without it Blender would sit through the whole job timeout before
' falling back to writing the PSD itself.
'
' args(0) = jsx path
' args(1) = job folder (passed to the jsx, and where fail.txt is written)

Dim app, args, jsxPath, jobDir, fso, f

Set args = WScript.Arguments
If args.Count < 2 Then
    WScript.Quit
End If

jsxPath = args(0)
jobDir = args(1)

On Error Resume Next
    Set app = GetObject(, "Photoshop.Application")

    If Err.Number <> 0 Then
        Err.Clear
        Set fso = CreateObject("Scripting.FileSystemObject")
        Set f = fso.CreateTextFile(fso.BuildPath(jobDir, "fail.txt"), True)
        f.Write "no_photoshop"
        f.Close
    Else
        Dim jsxArgs(0)
        jsxArgs(0) = jobDir
        app.DoJavaScriptFile jsxPath, jsxArgs

        ' DoJavaScriptFile itself failing (busy, modal dialog up) would also
        ' leave no result file, so record that rather than stalling Blender.
        If Err.Number <> 0 Then
            Err.Clear
            Set fso = CreateObject("Scripting.FileSystemObject")
            If Not fso.FileExists(fso.BuildPath(jobDir, "result.json")) Then
                Set f = fso.CreateTextFile(fso.BuildPath(jobDir, "fail.txt"), True)
                f.Write "jsx_failed"
                f.Close
            End If
        End If
    End If
On Error GoTo 0
