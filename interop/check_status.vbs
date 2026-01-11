Option Explicit
Dim app, targetPath, doc, isUnsaved
Dim args, fso, scriptDir, alertJsxPath, alertTrigger

Set args = WScript.Arguments
If args.Count = 0 Then WScript.Quit

targetPath = args(0)
isUnsaved = "FALSE" ' assume clean/closed

alertTrigger = False
If args.Count > 1 Then
    If UCase(args(1)) = "TRUE" Then alertTrigger = True
End If

On Error Resume Next
    Set app = GetObject(, "Photoshop.Application")
    If Err.Number = 0 Then
        
        If alertTrigger Then
             Set fso = CreateObject("Scripting.FileSystemObject")
             scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
             alertJsxPath = fso.BuildPath(scriptDir, "alert.jsx")
             app.DoJavaScriptFile alertJsxPath
        End If

        For Each doc In app.Documents
            If LCase(doc.FullName) = LCase(targetPath) Then
                If Not doc.Saved Then
                    isUnsaved = "TRUE"
                End If
                Exit For
            End If
        Next
    End If
On Error GoTo 0

WScript.StdOut.Write isUnsaved

