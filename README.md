# Nano Whiteboard Doctor

A desktop GUI tool that transforms messy whiteboard photos into clean, polished graphics using [Fal AI's Nano Banana 2](https://fal.ai/models/fal-ai/nano-banana-2/edit) image-to-image model.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![PyQt6](https://img.shields.io/badge/GUI-PyQt6-41cd52)

## Before & After

### Chalkboard Style
![Chalkboard before/after](samples/demo1_before_comparison_chalkboard.png)

### Blueprint Style
![Blueprint before/after](samples/demo2_before_comparison_blueprint.png)

### Pixel Art Style
![Pixel Art before/after](samples/demo3_before_comparison_pixel-art.png)

### Neon Sign Style
![Neon Sign before/after](samples/030426_comparison_neon-sign.png)

### Corporate Clean Style
![Corporate Clean before/after](samples/IMG20260405125048_comparison_corporate-clean.png)

More samples available in the [Sample-Whiteboards](https://github.com/danielrosehill/Sample-Whiteboards) companion repo.

## What It Does

Take a photo of your messy whiteboard and Nano Whiteboard Doctor will:
- Clean up handwriting and sketches
- Add polished labels and icons
- Produce a professional-looking diagram
- Apply any of **24 built-in style presets** or a fully custom prompt

Supports **single image** or **batch processing** of multiple whiteboard photos at once.

## Screenshot

![GUI](screenshot/gui.png)

## Style Presets

24 presets across 5 categories. Each preset applies a distinct visual treatment while preserving all original whiteboard content.

### Professional

| Preset | Description |
|--------|-------------|
| Clean & Polished | Clear labels and icons on a white background -- the default |
| Corporate Clean | Minimalist corporate slide-ready diagram |
| Hand-Drawn Polished | Refined sketch -- designer's notebook feel |
| Minimalist Mono | Black and white, Bauhaus-inspired minimalism |
| Ultra Sleek | Thin lines, Swiss design aesthetic |

### Creative

| Preset | Description |
|--------|-------------|
| Colorful Infographic | Bold, vibrant infographic with rich colors |
| Comic Book | Graphic novel panel with ink outlines and Ben-Day dots |
| Isometric 3D | Isometric 3D-style boxes and depth |
| Neon Sign | Glowing neon tubes on a dark brick wall |
| Pastel Kawaii | Soft pastel palette with cute rounded forms |
| Pixel Art | Retro 16-bit pixel art style |
| Stained Glass | Cathedral stained glass with jewel tones |
| Sticky Notes | Colorful sticky notes on a cork board |
| Watercolor Artistic | Watercolor painting on textured paper |

### Technical

| Preset | Description |
|--------|-------------|
| Blueprint | Architectural blueprint on deep blue background |
| Dark Mode Technical | Engineering diagram on dark background |
| Flat Material | Google Material Design flat UI style |
| GitHub README | Markdown-friendly, repo architecture overview |
| Photographic | Photorealistic 3D render with glass and metal |
| Terminal Hacker | Green-on-black phosphor CRT terminal |
| Visionary Inspirational | Cosmic/futurist keynote aesthetic |

### Retro & Fun

| Preset | Description |
|--------|-------------|
| Chalkboard | Classic green chalkboard with chalk texture |
| Eccentric Psychedelic | Wild psychedelic maximum saturation |
| Mad Genius | Chaotic beautiful-mind inventor's notebook |
| Retro 80s Synthwave | Neon 1980s synthwave with grid lines |
| Woodcut | Medieval woodcut/linocut print on parchment |

### Language

| Preset | Description |
|--------|-------------|
| Bilingual Hebrew | English + Hebrew labels side by side |
| Translated Hebrew | Fully translated to Hebrew with RTL layout |

## Install

### Option A: Debian package (.deb)

Download the `.deb` from [Releases](https://github.com/danielrosehill/Nano-Whiteboard-Doctor/releases) and install:

```bash
sudo dpkg -i nano-whiteboard-doctor_0.1.0_all.deb
nano-whiteboard-doctor
```

### Option B: Run from source with uv

```bash
git clone https://github.com/danielrosehill/Nano-Whiteboard-Doctor.git
cd Nano-Whiteboard-Doctor
uv sync
uv run nano-whiteboard-doctor
```

### Get a Fal AI API key

Sign up at [fal.ai](https://fal.ai) and grab your API key from the dashboard. On first run, you'll be prompted to enter it. The key is saved locally in `~/.config/nano-whiteboard-doctor/config.json`.

## Usage

1. Click **Add Images** to select one or more whiteboard photos
2. Choose a **Style Preset** from the dropdown (or write a custom prompt)
3. (Optional) Adjust output format, resolution, and aspect ratio
4. Click **Process** to send them through the AI
5. Cleaned images are saved to your chosen output directory

## Configuration

- **API Key**: Stored in `~/.config/nano-whiteboard-doctor/config.json`
- **Output Format**: PNG (default), JPEG, or WebP
- **Resolution**: 0.5K, 1K (default), 2K, or 4K
- **Aspect Ratio**: Auto (default), 1:1, 4:3, 16:9, and more

## Building the .deb

```bash
./build-deb.sh
```

Requires `uv`, `dpkg-deb`, and `fakeroot`.

## License

MIT
