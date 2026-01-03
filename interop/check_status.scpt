on run argv
    set targetPath to item 1 of argv
    tell application id "com.adobe.Photoshop"
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