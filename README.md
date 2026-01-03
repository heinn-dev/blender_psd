About
=========
Blender add-on (⚠️ very WIP and experimental, back up your files! ⚠️) that allows you to seamlessly edit a PSD file's layers in Photoshop and Blender at the same time. Any changes you make in Blender will immediately sync with Photoshop upon hitting save, and similarly, hitting save in Photoshop will see your changes immediately reflected in Blender.

<img width="311" height="513" alt="image" src="https://github.com/user-attachments/assets/5e46b5fb-ffae-49ed-b674-08b0ee48d7a0" />


## Photoshop Setup
- in the add-on preferences, add the full path to your Photoshop exe (e.g. `C:\Program Files\Adobe\Adobe Photoshop 2023\Photoshop.exe`)
- add `WarnRunningScripts 0` to PSUserConfig.txt to update the image in Photoshop silently

## Quickstart
- open the image editor, drag in a `.psd`
- on the sidebar / n-menu, select `BPSD`
- pick the image on the dropdown, and press `Sync file`

Pressing `Save` will update your changes in the .psd and Photoshop, if it is open. Only layers marked as dirty (`Image*`) will be saved in the psd. Note that pressing `Alt-S` to save the layer doesnt save the psd by default (you can enable this by clicking the toggle next to the save button, but it is quite slow). 
The psd preview will look black if Photoshop isn't running, as it is necessary to update the composite image.

⚠️ Warning ⚠️
=========
**Text Layers** can't be loaded or saved yet!

While there are some safety features built in (you can't overwrite the changes in Photoshop when saving from Blender if the file is unsaved and viceversa), I haven't tested this add-on throughoutly and *data loss may still occur*.

In general, if you see a blank layer in your layer list, do not save unless you really care about that layer.

Thanks
=========
This add-on uses an [hacked together fork](https://github.com/heinn-dev/PhotoshopAPI) of [PhotoshopAPI by EmilDohne](https://github.com/EmilDohne/PhotoshopAPI). It adds limited support for Adjustment Layers, namely loading and saving them from a file without losing data and being able to edit their mask.
