; launcher.ahk
; USAGE: AutoHotkey.exe launcher.ahk "PathToPS" "PathToJSX"

#NoEnv
SendMode Input
SetWorkingDir %A_ScriptDir%

; 1. Capture the current active window (Blender)
WinGet, active_id, ID, A

; 2. Read Arguments
ps_exe := A_Args[1]
script_path := A_Args[2]

if (ps_exe = "" or script_path = "")
{
    MsgBox, Error: Missing arguments for BPSD Launcher.
    ExitApp
}

; 3. Run Photoshop (Launch the script)
; We use 'Run' which does not block the script, allowing us to act immediately
Run, "%ps_exe%" "%script_path%"

; 4. The "Focus War" Mitigation
; We wait briefly for Photoshop to try and steal focus, then we steal it back.
; Loop for a short duration (e.g., 2 seconds) to catch the window pop-up.
Loop, 20
{
    ; If Photoshop becomes active...
    IfWinActive, ahk_class Photoshop
    {
        ; Force focus back to our captured window (Blender)
        WinActivate, ahk_id %active_id%
        break
    }
    Sleep, 100
}

ExitApp