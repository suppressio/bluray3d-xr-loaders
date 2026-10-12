🌐 [English](README.md) | **Italiano**

# bluray3d-xr loaders

Animazioni di caricamento per [bluray3d-xr-glasses-linux](https://github.com/suppressio/bluray3d-xr-glasses-linux):
il breve loop che un player mostra dopo un salto nel film, mentre il disco ci arriva.

Fatte da zero in Blender con script Python: niente immagini, niente font esterni,
niente di altri, così possono essere distribuite insieme al programma.

| Script | Cosa | Output |
|---|---|---|
| `loader_retrowave.py` | una griglia al neon che corre verso l'orizzonte, un disco olografico che ci sorge sopra come il sole, una barra di caricamento fatta di barre di equalizzatore che saltano a tempo, "LOADING" (4 s) | 1920x1080, oppure 3D side-by-side 3840x1080 con `--sbs` |
| `loader_simple.py` | un disco visto dall'alto, un arco che gira, "LOADING..." (2 s) | 1920x1080 |

Ogni movimento fa un numero intero di giri o di cicli per loop: il loop non ha giunture.
L'animazione usa driver sul numero di fotogramma, non keyframe (stabili tra le versioni
di Blender; scritto per Blender 5).

## Render

```console
blender -b -P loader_retrowave.py -- retrowave.mp4 --sbs
blender -b -P loader_retrowave.py -- retrowave-2d.mp4
blender -b -P loader_simple.py -- simple.mp4
```

Il programma le distribuisce come `loaders/retrowave.mp4` (quella side-by-side: i film
3D la mostrano in 3D, quelli 2D il suo occhio sinistro) e `loaders/simple.mp4`, scelte
con `--loader retrowave` (il default) o `--loader simple`.

Per guardare una scena o modificarla: apri Blender, scheda Scripting, apri lo script,
Run Script, poi guarda dalla camera (tastierino 0) e avvia la riproduzione (Spazio).

## Licenza

[MIT](LICENSE), come il programma.
