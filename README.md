# bluray3d-xr loaders

Loading animations for [bluray3d-xr-glasses-linux](https://github.com/suppressio/bluray3d-xr-glasses-linux):
the short loop a player shows after a jump in the movie, while the disc gets there.

Built from scratch in Blender with Python scripts: no images, no external fonts,
nothing of anyone else's, so they can be shipped with the program.

| Script | What | Output |
|---|---|---|
| `loader_retrowave.py` | a neon grid running to the horizon, a holographic disc rising on it like the sun, a loading bar of equalizer bars jumping to the beat, "LOADING" (4 s) | 1920x1080, or side-by-side 3D 3840x1080 with `--sbs` |
| `loader_simple.py` | a disc seen from above, a spinning arc, "LOADING..." (2 s) | 1920x1080 |

Every motion is a whole number of turns or cycles per loop: the loop has no seam.
Animation uses drivers on the frame number, not keyframes (stable across Blender
versions; written for Blender 5).

## Render

```console
blender -b -P loader_retrowave.py -- retrowave.mp4 --sbs
blender -b -P loader_retrowave.py -- retrowave-2d.mp4
blender -b -P loader_simple.py -- simple.mp4
```

The program ships them as `loaders/retrowave.mp4` (the side-by-side one: 3D
movies show it in 3D, 2D movies its left eye) and `loaders/simple.mp4`, chosen
with `--loader retrowave` (the default) or `--loader simple`.

To look at a scene or change it: open Blender, Scripting tab, open the script,
Run Script, then look through the camera (Numpad 0) and play (Space).

## License

[MIT](LICENSE), like the program.
