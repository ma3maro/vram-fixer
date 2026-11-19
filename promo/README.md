# Editable comparison loops

`index.html` is the burning-room loop. `../promo-pressure/index.html` is the separate 8 GB pressure-test loop. Each is 1080×1350, eight seconds, silent and deterministic. These are comparison animations of real rendered stills, not animated fire simulations or captured UI recordings.

```bash
npm install
npm run check
npx hyperframes preview --background
npx hyperframes render --quality delivery --fps 30 --output ../media/room-comparison.mp4
npx hyperframes render --format gif --fps 15 --output ../media/room-comparison.gif
```

`build_promos.py` regenerates both HTML projects and the three still PNG cards from the published evidence. It needs Pillow. Font notices and the GSAP dependency notice are in assets. The wipe is adapted from the retained HyperFrames registry component; no selective treatment is applied to either image.

Numbers must remain tied to their case and measurement labels. The pressure test's BEFORE already rendered through system RAM. Do not replace the qualification with an unsupported failed-render rescue story.
