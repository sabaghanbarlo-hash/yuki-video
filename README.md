# Call of Yuki video generator

Give it an English script, get an explainer video with the animated chibi narrator
(moving mouth, walking, changing backgrounds, text/icon/list/compare cards, captions + .srt).

## Run on GitHub (free)
Actions > Generate video > Run workflow > pick a script in `stories/` > download the `video` artifact.

## Run locally
    pip install pillow numpy edge-tts   # plus ffmpeg
    python generate.py stories/sample.txt

## Script format
Plain paragraphs. `# Title` sets the title card, `## Heading` starts a section.
Optional cues at the start of a paragraph: `[loop: Title :: A | B | C]`,
`[compare: Left :: a | b || Right :: c | d]`, `[list: Title :: a | b | c]`.
Everything else is directed automatically.

## Your own voice
    python generate.py stories/x.txt --export-beats     # lists numbered beats
Record each beat as `001.wav`, `002.mp3` ... in a folder, then
    python generate.py stories/x.txt --audio-dir myvoice
Mouth sync follows your recording. `--tts babble` is an offline test sound, not speech.
