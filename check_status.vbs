Option Explicit
Dim app, targetPath, doc, isUnsaved
Dim args

Set args = WScript.Arguments
If args.Count = 0 Then WScript.Quit

targetPath = args(0)
isUnsaved = "FALSE" ' Default assume clean/closed

On Error Resume Next
    Set app = GetObject(, "Photoshop.Application")
    If Err.Number = 0 Then
        ' Loop documents to find the match
        For Each doc In app.Documents
            ' VBScript string comparison
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