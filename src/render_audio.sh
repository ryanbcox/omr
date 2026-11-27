#!/usr/bin/env bash
# Render the MIDI to MP3 with a piano soundfont (MuseScore General, Salamander-derived grand).
set -euo pipefail
cd "$(dirname "$0")/.."
SF=${SF:-/usr/share/sounds/sf2/MuseScore_General_Full.sf2}
MID=output/living_the_gospel_of_jesus_christ.mid
WAV=$(mktemp --suffix=.wav)
fluidsynth -ni -q -g 0.6 -r 44100 -R 1 -C 0 \
  -o synth.reverb.room-size=0.45 -o synth.reverb.level=0.5 -o synth.reverb.width=0.8 \
  -F "$WAV" "$SF" "$MID"
# trim leading silence, keep a natural decay at the end, normalize loudness
ffmpeg -y -loglevel error -i "$WAV" \
  -af "silenceremove=start_periods=1:start_threshold=-60dB,apad=pad_dur=1,areverse,silenceremove=start_periods=1:start_threshold=-70dB,afade=t=in:st=0:d=0.5,areverse,loudnorm=I=-16:TP=-1.5:LRA=11" \
  -ar 44100 -codec:a libmp3lame -b:a 192k \
  -metadata title="Living the Gospel of Jesus Christ (piano accompaniment)" \
  -metadata artist="Kathleen Kelly and Natalie Adams" \
  output/living_the_gospel_of_jesus_christ.mp3
rm -f "$WAV"
ffprobe -v error -show_entries format=duration -of csv=p=0 output/living_the_gospel_of_jesus_christ.mp3
