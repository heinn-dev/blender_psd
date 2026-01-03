-- actually unused

on run argv
    set jsxPath to item 1 of argv
    
    tell application "Adobe Photoshop 2024"
        do javascript file jsxPath
    end tell
end run