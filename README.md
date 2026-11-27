# Living the Gospel of Jesus Christ: piano accompaniment MIDI and MP3

This is a piano-only performance of *Living the Gospel of Jesus Christ* (words and music by Kathleen Kelly and Natalie Adams, © 2026 IRI). It plays the written introduction followed by all four verses, in the manner of the *Hymns for Home and Church* accompaniment recordings.

## Output
| File | What it is |
|---|---|
| `output/living_the_gospel_of_jesus_christ.mp3` | Piano render, 192 kbps, about 3:01 |
| `output/living_the_gospel_of_jesus_christ.mid` | Expressive MIDI: RH and LH tracks, tempo map, sustain pedal |
| `output/living_the_gospel_of_jesus_christ_girl_solo.mp3` | Piano + synthesized solo girl's voice (about 8–10 years old) |
| `output/living_the_gospel_of_jesus_christ_childrens_chorus.mp3` | Piano + a small synthesized children's chorus (5 voices) |
| `output/living_the_gospel_of_jesus_christ_with_melody.mid` | Piano MIDI plus a melody track with lyric (karaoke) events |
| `output/*_written.musicxml` | Transcription in printed order (with repeat endings) |
| `output/*_performed.musicxml` | The same music unrolled in performed order |

## How the music plays
- **Form:** the written 4-bar intro ends on a fermata. "Oh, the" is the pickup into verse 1. Verses 1–3 take the 1st/2nd/3rd ending, whose piano tag has a fermata and then the pickup into the next verse. Verse 4 takes the 4th ending, with a *rit.* and a final fermata.
- **Tempo and feel:** ♩ = 96 (the score marks 92–100), with straight eighths.
- **What's played:** the piano part exactly as printed, melody included in the RH. There is no voice track.
- **Phrasing:**
  - The tempo broadens slightly into each fermata.
  - The melody is voiced above the inner chord tones.
  - The chorus ("I can live, I can care…") gets a small lift, a little more on the last verse.
  - The sustain pedal changes with the harmony.
  - Timing and velocity are lightly humanized.

## Vocals

> To swap in natural, neural child voices on a machine with Hugging Face access, see **[HANDOFF.md](HANDOFF.md)**.

- **Melody and lyrics:** `src/lyrics.py` reads the lyric syllables and their x positions from the PDF's text layer. It attaches each syllable to the melody note under it, handling:
  - verse-specific lyrics (the "I will" / "I'll pre-" pickups and the "— —" rests)
  - melismas ("see!", "Lord's", "nite,")
  - the "2./3./4. Oh, the" pickups in the first ending
- **Singing synthesis:** `src/sing.py` uses [MBROLA](https://github.com/numediart/MBROLA) diphone singing with the `us1` voice and [eSpeak NG](https://github.com/espeak-ng/espeak-ng) phonemes, plus a few hand-fixed syllable splits.
  - Notes have controlled pitch: a glide into each note, delayed light vibrato, and breaths at phrase ends.
  - For a child's timbre, each voice is synthesized with pitch ÷ k and duration × k, then resampled by k. That keeps the pitch and timing and raises the formants (k ≈ 1.17 for the solo).
- **Chorus:** five voices, each with its own formant ratio (1.13–1.25), detune, vibrato and timing scatter, panned across the stereo field, with more reverb than the solo.
- **Limits:** this is diphone synthesis, so the voices sound synthetic rather than like a real recorded child. Neural singing models weren't reachable from the build environment.

## How the transcription was made
1. **Vector OMR** (`tools/pdf_vector_omr.py`): the PDF is Finale output that uses a SMuFL font. The script reads every notehead, dot, flag, rest and fermata glyph, plus the staff, stem and beam geometry, directly from the vectors. That gives exact pitches.
2. **Visual check:** each bar was checked against 300/600-dpi renders for rhythm, voices, ties and fermatas, then encoded in `src/transcription.py`.
3. **Independent image OMR:** the pages were also run through [homr](https://github.com/liebharc/homr).
   - It agreed with the transcription on all 356 note pitches but one.
   - At that note, a zoomed 600-dpi render confirmed the transcription (F#3 in the final Bm chord).
4. **Round trip:** the MusicXML was re-engraved with [Verovio](https://www.verovio.org/) (`docs/transcription_render.png`) and compared with the PDF.

## Rebuild
```bash
pip install music21 mido pymupdf verovio
apt-get install fluidsynth musescore-general-soundfont-lossless ffmpeg
python3 src/build.py          # checks every bar's duration, writes MusicXML + MIDI
./src/render_audio.sh         # MIDI -> MP3 (MuseScore General grand piano)
apt-get install mbrola mbrola-us1 espeak-ng sox
python3 src/sing.py solo      # piano + girl solo
python3 src/sing.py chorus    # piano + small children's chorus
python3 src/sing.py midi      # MIDI with melody/lyrics track
```
