on run argv
    set targetPath to item 1 of argv
    set triggerAlert to false
    
    if length of argv > 1 then
        if item 2 of argv is "TRUE" then
            set triggerAlert to true
        end if
    end if

    tell application id "com.adobe.Photoshop"
        if triggerAlert then
            -- Logic to run alert.jsx would go here. 
            -- Requires resolving path to alert.jsx relative to this script.
            -- do javascript file jsxPath
        end if

        repeat with d in documents
            try
                if (posix path of (file path of d as alias)) is targetPath then
                    return modified of d
                end if
            end try
        end repeat
    end tell
    return false
end run