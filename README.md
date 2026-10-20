# Podcasts

A terminal podcast player for the Pi. Pick a show, pick an episode, and listen. Your place is saved in every episode, so you can stop and come back later.

## Run

```
bash app-store.sh install
bash app-store.sh run
```

## Adding episodes

Put .wav files in folders under `~/podcasts` - one folder per show:

```
~/podcasts/Japanese While You Sleep/Episode 1.wav
~/podcasts/Japanese While You Sleep/Episode 2.wav
```

New episodes show up the next time you start the app. An optional `cover.txt` in a show's folder becomes its artwork on the player screen.

## Playing

- Up/Down and Enter to pick a show and an episode.
- Space plays and pauses. Left/Right skips 10 seconds. `R` restarts the episode. `q` goes back.
- Episodes you started show a resume marker with your timestamp; finished ones show "done".

Playback uses `aplay` (ALSA), already on DietPi - nothing to install. Progress saves automatically every few seconds and whenever you pause or leave.

## Languages

Works with the Translations app (English, Espanol, Francais, Deutsch). Without it, it runs in English.

MIT, built with AI assistance from my design.
