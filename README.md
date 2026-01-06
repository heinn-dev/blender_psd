About
=========
Experimental Blender (4.x) add-on that allows you to seamlessly edit a PSD file's layers in Photoshop and Blender at the same time. Any changes you make in Blender will immediately sync with Photoshop upon hitting save, and similarly, hitting save in Photoshop will see your changes immediately reflected in Blender. 
There's also an approximate live preview of the PSD composite, among some features to make it easier to paint.

<img width="316" height="675" alt="Screenshot 2026-01-05 022542" src="https://github.com/user-attachments/assets/39ac22a0-6c16-4c14-ba8b-ba86d81234bb" />

## Download & Install
[Download Latest Release (Zip)](https://github.com/heinn-dev/blender_psd/releases/latest/download/release.zip)
Drag into Blender or go to `Preferences > Add-ons > Install from disk`

## How to use
- add `WarnRunningScripts 0` to PSUserConfig.txt to update the image in Photoshop silently
- in Blender, open the image editor, drag in a .psd
- on the sidebar / n-menu, select `BPSD`
- pick the image on the dropdown, and press `Sync file`
- click on a layer in the layer hierarchy to preview it in the image editor window
- clicking on a layer also selects it as the active texture in paint mode (set the material slot menu to "Single Image" mode)

- to live-preview your changes, press the `Make Nodes` button and select the material output
  - if you have the material set up, you can hide layers by clicking the dot on the hierarchy
  - you can shift click this dot to reset it to the .psd's visibility
  - you can press the button below the layers to toggle between the psd output and the live composite / focus the image editor on the psd

Note that for the psd to update after saves, Photoshop must be open.

## Saving
Pressing `Save` will update your changes in the .psd and Photoshop, if it is open. Only layers marked as dirty (`Layer*`) will be saved in the psd. You can force it to save every loaded layer by shift-clicking the `Save` button. 

Note that pressing `Alt-S` to save the layer doesnt save the psd by default (you can enable this by clicking the toggle next to the save button, but it is quite slow). 

⚠️ Warning ⚠️
=========

⚠️ Text Layers (and other more niche types of layers) can't be loaded or saved yet! If you see a blank layer in your layer list (named "UNKNOWN"), do not save unless you really don't care about that layer. 

⚠️ Linked Layers are a bit funky. Ensure that the image is correctly linked in Photoshop, or the file wont load correctly.

⚠️ While there are some safety features built in (you can't overwrite the changes in Photoshop when saving from Blender if the file is unsaved and viceversa, and it will warn you), it's easy sometimes to not keep track of unchanged saves and have the two programs desync. You can always manually reload from disk in Photoshop (F12) or on the add-on.

Thanks
=========
This add-on uses an [hacked together fork](https://github.com/heinn-dev/PhotoshopAPI) of [PhotoshopAPI by EmilDohne](https://github.com/EmilDohne/PhotoshopAPI). It adds limited support for Adjustment Layers, namely loading and saving them from a file without losing data and being able to edit their mask.
