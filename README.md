About
=========
Experimental Blender (4.x) add-on that allows you to seamlessly edit a PSD file's layers in Photoshop and Blender at the same time. Any changes you make in Blender will immediately sync with Photoshop upon hitting save, and similarly, hitting save in Photoshop will see your changes immediately reflected in Blender. 
There's also an approximate live preview of the PSD composite.

<img width="311" height="513" alt="image" src="https://github.com/user-attachments/assets/5e46b5fb-ffae-49ed-b674-08b0ee48d7a0" />

## How to use
- add `WarnRunningScripts 0` to PSUserConfig.txt to update the image in Photoshop silently
- open the image editor, drag in a `.psd`
- on the sidebar / n-menu, select `BPSD`
- pick the image on the dropdown, and press `Sync file`
- click on a layer in the layer hierarchy to preview it in the image editor window
- clicking on a layer also selects it as the paintable texture in paint mode (set the material slot menu to "Single Image" mode)
- to live-preview your changes, press the `Make Nodes` button and hook it up to a material output
  - if you have the material set up, you can hide layers by clicking the dot on the hierarchy
  - you can shift click this dot to reset it

- after a `Save`, clicking on the filename below the layers will focus the reloaded psd with your changes
- 

Pressing `Save` will update your changes in the .psd and Photoshop, if it is open. Only layers marked as dirty (`Image*`) will be saved in the psd. Note that pressing `Alt-S` to save the layer doesnt save the psd by default (you can enable this by clicking the toggle next to the save button, but it is quite slow). 
The psd preview will look black if Photoshop isn't running, as it is necessary to update the composite image.

⚠️ Warning ⚠️
=========
While there are some safety features built in (you can't overwrite the changes in Photoshop when saving from Blender if the file is unsaved and viceversa), I haven't tested this add-on throughoutly and **data loss may still occur!** Back up your files!.

Still investigating a bug where some layers will be straight up blank upon loading. If you edit that layer and save it, it will be nuked. There's a jank workaround for now : move that layer so that it goes out of bounds, draw something there, restore the layer position. It should then load fine.

Text Layers (and other more niche types of layers) can't be loaded or saved yet! If you see a blank layer in your layer list (named "UNKNOWN"), do not save unless you really care about that layer. 

Thanks
=========
This add-on uses an [hacked together fork](https://github.com/heinn-dev/PhotoshopAPI) of [PhotoshopAPI by EmilDohne](https://github.com/EmilDohne/PhotoshopAPI). It adds limited support for Adjustment Layers, namely loading and saving them from a file without losing data and being able to edit their mask.
