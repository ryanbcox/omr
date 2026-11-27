# HANDOFF: replace the synthetic child voices with natural-sounding ones

You are picking up a project on a machine that **can** download from Hugging Face, GitHub releases and PyPI. The previous environment could not, so the sung versions use MBROLA diphone synthesis, which sounds robotic. Your job is to make the **girl solo** and the **small children's chorus** sound like real children singing. Keep everything else as it is.

Read this whole file before acting. Then work through **Task 1**, and fall back to **Task 2** or **Task 3** only if Task 1 can't reach the quality bar.

---

## 1. What exists (don't redo it)

The song is *Living the Gospel of Jesus Christ* (Kathleen Kelly & Natalie Adams, © 2026 IRI). It may be copied for incidental, noncommercial Church or home use, so keep every output private and noncommercial.

| Path | What it is | Status |
|---|---|---|
| `score/living_the_gospel_of_jesus_christ.pdf` | Source score | input |
| `src/transcription.py` | Piano part, verified bar by bar (vector OMR, visual check, homr cross-check) | **final, don't edit** |
| `src/build.py` | → piano MIDI (tempo map, fermatas, rit., pedal) + MusicXML | final |
| `output/living_the_gospel_of_jesus_christ.mid` / `.mp3` | Piano-only accompaniment: written intro + 4 verses, ♩=96, straight 8ths | **final** |
| `src/lyrics.py` | Melody + lyric syllables aligned per verse, read from the PDF text layer | final |
| `output/vocal_score.json` | **Engine-neutral vocal score** (format below) | input for you |
| `output/living_the_gospel_of_jesus_christ_with_melody.mid` | Piano + "Melody" track (ch. 2) with `lyrics` meta events | input for you |
| `output/stems_flac/piano.flac` | Piano stem, 44.1 kHz stereo | input |
| `output/stems_flac/solo_1_dry.flac` | Dry MBROLA **guide vocal**, solo: correct pitch, timing and words, robotic timbre | input |
| `output/stems_flac/chorus_{1..5}_dry.flac` | Five dry MBROLA chorus guides, each slightly detuned, timing-scattered, different formants | input |
| `src/sing.py` | MBROLA synthesis + the mixer (`remix` command, see §4) | reuse the mixer |
| `tools/check_vocals.py` | Timing + pitch checker for a replacement vocal | use it |
| `output/*_girl_solo.mp3`, `output/*_childrens_chorus.mp3` | Current robotic versions | to be superseded |

**Shared timeline:** every audio file and every time in `vocal_score.json` starts at **MIDI tick 0 = 0.000 s**. The piano is about 3:03 before trimming, and the first sung note ("Oh,") is at 11.08 s. A replacement vocal must keep this timeline exactly. Pad or trim to match; never time-stretch.

### `vocal_score.json` format
```json
{"phrases": [ {"start": 11.08, "end": 19.4, "notes": [
   {"start": 11.0771, "end": 11.4104, "midi": 57, "note": "A3", "lyric": "Oh,", "word": "Oh",
    "slur": false, "phonemes_sampa": ["@U"], "phonemes_arpabet": ["ow"]}, ...]}, ...]}
```
- 39 phrases, 281 notes, in the order sung: intro (no singing), then verse 1, 2, 3 and 4.
- `slur: true` marks a melisma continuation note. Its `lyric` is `"-"` and it carries no phonemes; the syllable continues from the previous note.
- A phrase boundary is a breath.
- Times are note boundaries on the beat. The MBROLA guide places onset consonants slightly *before* `start`, the way a singer does.
- Range is A3–B4 (written pitch). That's comfortable for children; don't transpose.

---

## 2. Quality bar (what "done" means)
1. **Sound:** it sounds like a child, roughly 8–10 years old: light, slightly breathy, little or no vibrato, not an adult soprano. The chorus sounds like about 5 children, not one voice doubled.
2. **Words:** you can understand them. Run Whisper (e.g. `openai/whisper-large-v3` from HF) on the dry vocal and compare it with the lyrics (§6). Aim for at least 85% word accuracy on the solo.
3. **Timing:** `tools/check_vocals.py NEW.wav` gives an overall offset within ±20 ms and a worst phrase offset of 40 ms or less.
4. **Pitch:** the same checker gives a median of 30 cents or less, and at most 10% of notes over 100 cents. For comparison, the MBROLA guide scores 17–23 cents and about 5%.
5. **Final mix:** made with the existing mixer (`python3 src/sing.py remix ...`), so the piano and the loudness (-16 LUFS) match the piano-only MP3.
6. **Clean output:** no artifacts (clicks, metallic buzz, octave jumps) on long held notes, especially "nite," (a 2-beat melisma) and the final "Christ." (fermata).

---

## 3. Approach

### Task 1 (recommended, fully scriptable): singing voice conversion of the guide vocals
The guide stems already have the right pitch, timing and phonemes. A **singing voice conversion** (SVC) model only has to swap the timbre to a child's voice.

**Suggested tool:** [Seed-VC](https://github.com/Plachtaa/seed-vc). It does zero-shot voice conversion, has a singing mode that keeps the source pitch contour, and downloads its checkpoints from Hugging Face on first run. Check its README for the current CLI. At the time of writing it is roughly:
```bash
python inference.py --source output/stems_flac/solo_1_dry.flac --target ref/child_ref_A.wav \
  --output conv/ --diffusion-steps 30 --length-adjust 1.0 --inference-cfg-rate 0.7 \
  --f0-condition True --auto-f0-adjust False --semi-tone-shift 0
```
- `--f0-condition True` is the singing model, and it keeps the melody.
- `--auto-f0-adjust False` and `--semi-tone-shift 0` stop it from moving the pitch toward the reference speaker's range.
- `--length-adjust 1.0` is required, or the timeline breaks.
- If the input is too long for one pass, split it at the breath points between phrases (`vocal_score.json` phrase boundaries, cut in the silences), convert each chunk, then put the chunks back at their original sample offsets.

**Alternatives** if Seed-VC is unavailable or weak: [RVC](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI) or [so-vits-svc](https://github.com/svc-develop-team/so-vits-svc). Both need a trained model of a target voice; use the RMVPE f0 extractor and a transpose of 0.

**Reference / target voices: consent matters.**
- Use only voices you have the right to use for synthesis:
  - recordings of the user's own family, made with a parent's or guardian's consent, or
  - voices explicitly licensed for voice conversion / AI use (check the license on the model card).
- **Do not** clone an identifiable real child or a known singer (celebrities, YouTube kids' choirs, Primary recordings, the Church's own recordings, etc.).
- If no suitable child reference exists, ask the user to record 10–30 s of a child singing anything clean, with no accompaniment and little reverb. A light adult female voice also works as a fallback; then apply the formant lift described next.

**Making it child-like** if the result sounds too adult:
- The guides already have raised formants (k = 1.13–1.25). If the converter normalizes them back, try a reference with a younger, lighter voice.
- Or post-process with a formant shift of about +10–15% that preserves pitch: `rubberband --formant -p 0` on a pitch-shifted copy, or a WORLD vocoder (`pyworld`) spectral-envelope warp.
- Keep vibrato minimal; children rarely use it. The guides have light vibrato, so if the converter exaggerates it, smooth the f0 in RVC (`--f0-filter` / median filter) or, in Seed-VC, regenerate the guide with lower vibrato. See `SINGERS` in `src/sing.py` (`vib_depth`), then `python3 src/sing.py stems`, which needs mbrola/espeak-ng/fluidsynth, available on Linux and WSL.

**Chorus (about 5 children, "very small"):**
- Convert `chorus_1..5_dry.flac` **separately**, ideally with 3–5 *different* child references, or one reference with different seeds and diffusion settings.
- Don't reuse one converted file 5 times: identical copies phase and comb-filter.
- Keep each converted voice's length and alignment.

**Then (all tasks):**
```bash
mkdir -p conv_final
# name the files exactly: solo_1.wav   or   chorus_1.wav ... chorus_5.wav  (.flac also accepted)
python3 tools/check_vocals.py conv_final/solo_1.wav output/stems_flac/solo_1_dry.flac
python3 src/sing.py remix solo   conv_final    # -> output/living_the_gospel_of_jesus_christ_girl_solo_neural.mp3
python3 src/sing.py remix chorus conv_final    # -> output/..._childrens_chorus_neural.mp3
```
The mixer normalizes each voice, pans the chorus (−0.45…+0.45), adds reverb (lighter on the solo), puts the voice about 3 dB above the piano, trims, and loudness-normalizes to −16 LUFS. With the original dry stems it reproduces the committed MP3s to within −48 dB, so it has been verified.

### Task 2 (if Task 1 can't pass the bar): score-to-singing synthesis
Generate the voice straight from `vocal_score.json` with a neural singing synthesizer.
- **[DiffSinger](https://github.com/openvpi/DiffSinger)**, driven directly or through **[OpenUtau](https://github.com/stakira/OpenUtau)**, with an **English-capable** voicebank whose license permits this use.
- DiffSinger `.ds` input needs:
  - `ph_seq`, `ph_dur` (seconds), `ph_num` (phonemes per word / onset group)
  - `note_seq` (note names), `note_dur`, `note_slur`
  - optionally `f0_seq`
- Build these from `vocal_score.json`:
  1. Use `phonemes_arpabet`, then map it through the voicebank's own dictionary or phoneme set. Many English voicebanks use ARPAbet-like symbols, but check its `dsdict`.
  2. Put `SP` (silence) between phrases.
  3. Give each slurred note the vowel of the previous note.
  4. Place onset consonants before the note start: take their duration out of the previous vowel or silence, about 60–100 ms.
- Render phrase by phrase, put each phrase at `phrase.start` on the shared timeline, write `solo_1.wav`, and remix as above.
- If a child-like English DiffSinger voicebank doesn't exist, synthesize with the best light female voice, then convert with Task 1's SVC step.
- **OpenUtau route** (GUI, semi-manual): File → Import `output/living_the_gospel_of_jesus_christ_with_melody.mid`. The Melody track carries the lyrics: one `lyrics` event per syllable, with a trailing `-` meaning the word continues. Set the tempo map from the MIDI, choose the voicebank, render, export WAV and remix.

### Task 3 (manual fallback): commercial editors
[Synthesizer V Studio](https://dreamtonics.com/synthesizerv/) or [ACE Studio](https://acestudio.ai/) can import `..._with_melody.mid` with lyrics. Pick a youthful English voice, export dry WAV at 44.1 kHz from time 0, and run `remix`. This is a human step; tell the user rather than trying to automate a GUI.

---

## 4. Environment setup on the user's machine
```bash
git clone <this repo> && cd omr && git checkout claude/lds-hymn-midi-mp3-62u6lq
python3 -m venv .venv && . .venv/bin/activate
pip install numpy mido music21 pymupdf        # repo scripts
# ffmpeg and sox must be on PATH (brew install ffmpeg sox  |  apt install ffmpeg sox)
# For the SVC/TTS tool, use a separate venv and follow its README (PyTorch; CUDA or Apple MPS if available).
```
- `remix` and `check_vocals.py` need only numpy, mido, ffmpeg and sox. They use the committed `output/stems_flac/piano.flac`, so FluidSynth isn't required.
- Regenerating guides (`python3 src/sing.py stems`) also needs `mbrola`, `mbrola-us1`, `espeak-ng`, `fluidsynth` and the MuseScore General soundfont. That's easiest on Linux or WSL.

## 5. Things not to change
- `src/transcription.py`, the piano MIDI and the piano MP3: they've been verified against the score.
- The melody notes and lyric alignment in `vocal_score.json`. If you think a lyric is wrong, check it against the PDF before changing `src/lyrics.py`.
- The timeline (t = 0 = MIDI start).
- Don't commit large intermediate WAVs. `output/stems/` is git-ignored; commit only final MP3s and small scripts.

## 6. Verification checklist (run all, report numbers)
1. `python3 tools/check_vocals.py conv_final/solo_1.wav`, and the same for each chorus voice against its own guide (`output/stems_flac/chorus_N_dry.flac`). Record offset and pitch stats.
2. **Intelligibility.** Run Whisper on the dry converted solo and compare with the lyric text below:
   - Compute word accuracy per verse; target ≥ 85%. The repeated "Living the gospel of Jesus Christ" lines are the easiest, so weight the verse-specific lines.
   - Lyrics are in `vocal_score.json`: join the non-`-` lyrics per phrase.
3. **Listen**, or have the user listen, to these spots:
   - the 0:11 entrance
   - the "I can live, I can care" climax (about 0:31 in verse 1, on the MIDI timeline)
   - the "nite,___" melisma (about 0:39)
   - the final fermata
4. **Loudness:** `ffmpeg -i out.mp3 -af ebur128 -f null -` should read about −16 LUFS integrated.
5. Commit to branch `claude/lds-hymn-midi-mp3-62u6lq`. Name the outputs `..._girl_solo_neural.mp3` and `..._childrens_chorus_neural.mp3`, and update `README.md` with the model or tool used, the reference-voice source and license, and the checker numbers.
