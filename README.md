# Call of Yuki video generator

Turns a plain English script into a long video with the chibi narrator.

## Script format
```
# Video title
## Section name
Paragraph one (= one scene).

Paragraph two.
```

## Run
- **GitHub:** Actions -> "Generate video" -> Run workflow -> `stories/your-script.txt`. Download the `video` artifact (MP4 + SRT subtitles).
- **Local:** `pip install pillow numpy edge-tts` and have `ffmpeg` installed, then `python generate.py stories/sample.txt`

## Voice
- Default: free Edge voice (placeholder).
- Your own voice later: put recordings in a folder as `01.wav`, `02.mp3`, ... (one per paragraph, title card not counted) and run with `--audio-dir that-folder`. Fish Audio output plugs in the same way.
- `--tts none` renders silent timing for layout tests.

## Character
The narrator is `assets/narrator.png` (transparent PNG). Replace it, or pass `--sprite other.png`.
