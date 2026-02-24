on run argv
    set targetPath to item 1 of argv
    set triggerAlert to false

    if length of argv > 1 then
        if item 2 of argv is "TRUE" then
            set triggerAlert to true
        end if
    end if

    tell application id "com.adobe.Photoshop"
        -- First check if the target document is open and modified
        repeat with d in documents
            try
                if (posix path of (file path of d as alias)) is targetPath then
                    set isModified to modified of d

                    -- Only trigger alert if this specific file is unsaved
                    if triggerAlert and isModified then
                        -- Get path to alert.jsx relative to this script
                        set scriptPath to POSIX path of (path to me as text)
                        set AppleScript's text item delimiters to "/"
                        set pathItems to text items of scriptPath
                        set scriptDir to (items 1 thru -2 of pathItems) as string
                        set AppleScript's text item delimiters to ""
                        set alertJsxPath to "/" & scriptDir & "/alert.jsx"

                        do javascript (("$.evalFile('" & alertJsxPath & "')") as string)
                    end if

                    return isModified
                end if
            end try
        end repeat
    end tell
    return false
end run