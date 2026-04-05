#!/usr/bin/env python3
"""Whiteboard Makeover - Clean up whiteboard photos with Fal AI Nano Banana 2."""

import base64
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import unquote

import requests
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QAction, QDragEnterEvent, QDropEvent, QPixmap, QIcon
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

# --- Config ---

OLD_CONFIG_DIR = Path.home() / ".config" / "nano-whiteboard-doctor"
CONFIG_DIR = Path.home() / ".config" / "whiteboard-makeover"
CONFIG_FILE = CONFIG_DIR / "config.json"
CONFIG_VERSION = 3


def _migrate_config_dir():
    """One-time migration from old config directory name."""
    if OLD_CONFIG_DIR.is_dir() and not CONFIG_DIR.exists():
        shutil.copytree(str(OLD_CONFIG_DIR), str(CONFIG_DIR))
        (OLD_CONFIG_DIR / ".migrated_to_whiteboard_makeover").touch()


_migrate_config_dir()

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

ASPECT_RATIOS = ["auto", "1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3", "21:9", "9:21"]

# Core instructions shared by every preset -- style prompts build on top of this.
CORE_INSTRUCTIONS = (
    "Remove the physical whiteboard, markers, frame, and any background elements. "
    "Correct any perspective distortion so the output appears as a perfectly "
    "straight-on, top-down view regardless of the angle the original photo was taken from. "
    "Preserve all the original content, text, and diagrams. "
    "Where handwriting is ambiguous, infer the correct spelling from context rather than "
    "reproducing the raw strokes literally -- for example, a word that looks like "
    "'proxknox' should be rendered as 'Proxmox' if that is the obvious intended meaning."
)

# Ordered list of (key, display_name, category, prompt, default_aspect_ratio)
PROMPT_PRESETS = [
    # --- Professional ---
    ("clean_polished", "Clean & Polished", "Professional",
     "Take this whiteboard photograph and convert it into a beautiful and polished "
     "graphic featuring clear labels and icons. " + CORE_INSTRUCTIONS + " "
     "Output only the diagram on a clean white background. "
     "Keep the user's handwriting style and character but make it more legible and "
     "well-organized. The result should be a fully representative version of the "
     "whiteboard content that is much more visually attractive and easy to understand "
     "than the original photo.",
     "auto"),

    ("corporate_clean", "Corporate Clean", "Professional",
     "Take this whiteboard photograph and convert it into a clean, minimalist corporate "
     "diagram suitable for a professional presentation. " + CORE_INSTRUCTIONS + " "
     "Output only the diagram on a clean white background. Use a restrained color palette "
     "of navy blue, grey, and one accent color. Replace hand-drawn shapes with clean "
     "geometric forms, use a modern sans-serif font for all text, and add simple flat "
     "icons where appropriate. The result should look like it came from a polished slide "
     "deck -- professional, understated, and immediately readable.",
     "16:9"),

    ("hand_drawn_polished", "Hand-Drawn Polished", "Professional",
     "Take this whiteboard photograph and convert it into a polished hand-drawn style "
     "diagram. " + CORE_INSTRUCTIONS + " "
     "Output only the diagram on a clean white or light cream background. "
     "Keep the organic, hand-drawn character of the original but refine it -- smoother "
     "lines, consistent stroke weight, better spacing, and cleaner handwriting that is "
     "still clearly handwritten. Add soft watercolor-style fills or gentle color washes "
     "to different sections. The result should feel like a carefully crafted sketch in a "
     "designer's notebook -- warm, human, and thoughtfully composed.",
     "auto"),

    ("minimalist_mono", "Minimalist Mono", "Professional",
     "Take this whiteboard photograph and convert it into a stark, minimalist "
     "black-and-white diagram. " + CORE_INSTRUCTIONS + " "
     "Output only the diagram on a pure white background. Use only black lines, shapes, "
     "and text -- no color, no gradients, no fills. Lines should be clean and uniform "
     "weight. Use a simple, elegant sans-serif font. Maximize whitespace and let the "
     "structure breathe. The result should be austere and elegant -- like a diagram in "
     "an academic paper or a Dieter Rams design specification.",
     "auto"),

    ("ultra_sleek", "Ultra Sleek", "Professional",
     "Take this whiteboard photograph and convert it into an ultra-sleek, refined diagram "
     "with elegant precision. " + CORE_INSTRUCTIONS + " "
     "Output only the diagram on a pure white background with generous margins. "
     "Use extremely thin, hairline-weight lines in dark grey or black. Shapes should be "
     "geometric and perfectly aligned with consistent spacing. Use a single subtle accent "
     "color -- a muted teal or steel blue -- sparingly for key elements only. Text should "
     "be set in an ultra-light weight, elegant sans-serif font with generous letter "
     "spacing. Maximize negative space. The result should feel like it was designed by a "
     "Swiss typographer -- razor-sharp, breathtakingly clean, and effortlessly sophisticated.",
     "auto"),

    ("blog_hero", "Blog Hero", "Professional",
     "Take this whiteboard photograph and convert it into a polished diagram suitable as a "
     "blog post hero image. " + CORE_INSTRUCTIONS + " "
     "Output the diagram on a soft gradient background that transitions from light "
     "blue-grey at the top to white at the bottom. Use a modern, approachable color "
     "palette with one strong brand color (a confident blue or teal) and supporting warm "
     "greys. Shapes should have subtle rounded corners and light drop shadows for depth. "
     "Use a clean, highly readable sans-serif font. Add simple line icons that reinforce "
     "each concept. Include generous padding around the entire diagram. The result should "
     "be a 16:9 aspect ratio image ready to drop into a blog post as the featured image "
     "-- polished, professional, and inviting to click.",
     "16:9"),

    # --- Creative ---
    ("colorful_infographic", "Colorful Infographic", "Creative",
     "Take this whiteboard photograph and convert it into a bold, vibrant "
     "infographic-style diagram. " + CORE_INSTRUCTIONS + " "
     "Output only the diagram on a clean white background. Use a rich, vibrant color "
     "palette with distinct colors for different sections or concepts. Add colorful icons, "
     "rounded shapes, and visual hierarchy through size and color contrast. Text should be "
     "clear and legible in a friendly, rounded font. The result should feel energetic and "
     "engaging -- like a well-designed infographic you'd want to share.",
     "auto"),

    ("comic_book", "Comic Book", "Creative",
     "Take this whiteboard photograph and convert it into a comic book-styled diagram. "
     + CORE_INSTRUCTIONS + " "
     "Render everything in a bold comic book illustration style with thick black ink "
     "outlines, Ben-Day dot shading patterns, and a vivid primary color palette of red, "
     "blue, yellow, and green. Text should appear in comic-style lettering with key labels "
     "in speech bubbles or caption boxes. Add dynamic action lines and POW/ZAP-style "
     "emphasis marks around important connections. The result should look like a page "
     "ripped from a tech-themed graphic novel -- bold, punchy, and impossible to scroll past.",
     "3:4"),

    ("isometric_3d", "Isometric 3D", "Creative",
     "Take this whiteboard photograph and convert it into an isometric 3D-style diagram. "
     + CORE_INSTRUCTIONS + " "
     "Output only the diagram on a clean white background. Render boxes and containers as "
     "isometric 3D blocks with subtle depth and soft shadows. Use a modern, cheerful color "
     "palette with distinct colors for different components. Arrows and connectors should "
     "follow isometric angles. Labels should float cleanly above their elements. The "
     "result should look like a polished isometric tech illustration -- the kind you'd see "
     "in a modern SaaS landing page or developer documentation.",
     "4:3"),

    ("neon_sign", "Neon Sign", "Creative",
     "Take this whiteboard photograph and convert it into a diagram styled as glowing neon "
     "signs mounted on a dark brick wall. " + CORE_INSTRUCTIONS + " "
     "Output the diagram on a dark exposed-brick wall background. Render all lines, "
     "shapes, and text as glowing neon tubes in different colors -- pink, blue, white, and "
     "yellow. Each neon element should have a realistic glow effect with soft light "
     "bleeding onto the brick wall behind it. Connectors and arrows should be continuous "
     "neon tube bends. The result should look like an elaborate neon sign installation in "
     "a trendy bar -- atmospheric, eye-catching, and unmistakably cool.",
     "auto"),

    ("pastel_kawaii", "Pastel Kawaii", "Creative",
     "Take this whiteboard photograph and convert it into an adorable pastel-colored "
     "diagram in a kawaii illustration style. " + CORE_INSTRUCTIONS + " "
     "Output only the diagram on a soft pastel pink or lavender background. Use a soft "
     "pastel palette -- baby pink, mint green, lavender, peach, and sky blue. Shapes "
     "should have rounded, bubbly forms with thick soft outlines. Add tiny decorative "
     "elements like stars, sparkles, or small cloud accents. Use a cute, rounded "
     "handwriting-style font. The result should be charming and delightful -- like a page "
     "from a Japanese stationery notebook that still clearly communicates the diagram.",
     "auto"),

    ("pixel_art", "Pixel Art", "Creative",
     "Take this whiteboard photograph and convert it into a pixel art-styled diagram "
     "reminiscent of 16-bit era video games. " + CORE_INSTRUCTIONS + " "
     "Output on a clean background. Render all elements using visible, chunky pixels with "
     "a limited retro color palette. Shapes should be blocky with aliased edges. Text "
     "should use a pixel font. Add small pixel-art icons -- tiny servers, computers, "
     "clouds, gears -- next to relevant labels. Use dithering patterns for shading. The "
     "result should look like a UI screen from a classic strategy or simulation game -- "
     "charming, nostalgic, and instantly recognizable as pixel art.",
     "1:1"),

    ("stained_glass", "Stained Glass", "Creative",
     "Take this whiteboard photograph and convert it into a diagram styled as a stained "
     "glass window. " + CORE_INSTRUCTIONS + " "
     "Render each section as a pane of translucent colored glass with thick dark lead came "
     "lines separating them. Use rich jewel tones -- deep ruby, sapphire blue, emerald "
     "green, amber gold -- with light appearing to shine through the glass. Text should be "
     "integrated into the glass panes in a gothic or art nouveau lettering style. The "
     "result should look like a magnificent stained glass window depicting a technical "
     "diagram -- luminous, ornate, and strikingly beautiful.",
     "3:4"),

    ("sticky_notes", "Sticky Notes", "Creative",
     "Take this whiteboard photograph and convert it into a colorful sticky-note style "
     "diagram. " + CORE_INSTRUCTIONS + " "
     "Output the diagram on a light cork-board or soft beige textured background. Render "
     "each concept, box, or grouping as a colored sticky note (yellow, pink, blue, green) "
     "with a slight shadow and subtle rotation for a natural look. Use a casual "
     "handwritten-style font for text on the notes. Arrows and connectors should look "
     "like hand-drawn marker lines between the notes. The result should feel like a "
     "beautifully organized brainstorming board -- collaborative, creative, and approachable.",
     "4:3"),

    ("watercolor", "Watercolor Artistic", "Creative",
     "Take this whiteboard photograph and convert it into a beautiful watercolor-style "
     "illustrated diagram. " + CORE_INSTRUCTIONS + " "
     "Output only the diagram on a textured watercolor paper background. Paint each "
     "section and shape with soft, translucent watercolor washes in a harmonious palette "
     "of warm and cool tones. Lines should have an ink-pen quality -- thin, confident, "
     "and slightly organic. Text should be rendered in elegant calligraphic handwriting. "
     "The result should look like a page from a beautifully illustrated journal -- "
     "artistic, expressive, and unique.",
     "auto"),

    # --- Technical ---
    ("blueprint", "Blueprint", "Technical",
     "Take this whiteboard photograph and convert it into a diagram styled like an "
     "architectural blueprint. " + CORE_INSTRUCTIONS + " "
     "Output the diagram on a deep blue background. Use white and light blue lines for "
     "all shapes, arrows, and connectors. Text should appear in a clean technical drafting "
     "font. Add dimension-line styling to connectors and subtle cross-hatch fills where "
     "appropriate. The result should look like a precise engineering blueprint -- "
     "technical, authoritative, and classic.",
     "auto"),

    ("dark_mode", "Dark Mode Technical", "Technical",
     "Take this whiteboard photograph and convert it into a technical diagram with a dark "
     "background aesthetic. " + CORE_INSTRUCTIONS + " "
     "Output the diagram on a dark charcoal or near-black background. Use light-colored "
     "text (white or light grey) and neon or high-contrast accent colors like cyan, green, "
     "and orange for lines, arrows, and highlights. Use a monospace or technical font for "
     "labels. Add subtle grid lines or dot patterns in the background. The result should "
     "look like a technical blueprint or engineering schematic -- precise, detailed, and "
     "developer-friendly.",
     "auto"),

    ("flat_material", "Flat Material", "Technical",
     "Take this whiteboard photograph and convert it into a flat Material Design-styled "
     "diagram. " + CORE_INSTRUCTIONS + " "
     "Output only the diagram on a clean light grey (#FAFAFA) background. Use the "
     "Material Design color palette -- primary blues, teals, and deep oranges with clean "
     "flat fills and subtle elevation shadows on cards and containers. Round the corners "
     "of all shapes. Use the Roboto-style sans-serif font for all text. Icons should be "
     "simple outlined material-style icons. The result should look like a screen from a "
     "well-designed Android app -- clean, systematic, and modern.",
     "auto"),

    ("github_readme", "GitHub README", "Technical",
     "Take this whiteboard photograph and convert it into a clean diagram optimized for "
     "GitHub README files. " + CORE_INSTRUCTIONS + " "
     "Output only the diagram on a pure white background with clean edges and no border. "
     "Use GitHub's familiar color palette -- blues (#0969DA), greens (#1A7F37), purples "
     "(#8250DF), and neutral greys. Shapes should be clean rounded rectangles with subtle "
     "borders. Use a system sans-serif font. Add simple, recognizable developer icons "
     "(git branches, terminal prompts, API endpoints, databases). The result should look "
     "like a native GitHub diagram that blends seamlessly into a README.",
     "16:9"),

    ("photographic", "Photographic 3D", "Technical",
     "Take this whiteboard photograph and convert it into a photorealistic 3D-rendered "
     "diagram. " + CORE_INSTRUCTIONS + " "
     "Output the diagram on a clean surface like a light wooden desk or frosted glass "
     "table, shot from directly above. Render each box, container, or concept as a "
     "physical object -- glossy acrylic blocks, frosted glass cards, or brushed metal "
     "plates with realistic reflections and soft shadows. Arrows and connectors should "
     "look like thin metal rods or illuminated fiber-optic strips. Text should appear "
     "etched, printed, or embossed on the surfaces. Use studio-quality lighting with soft "
     "diffusion. The result should look like a product photograph of a physical scale "
     "model of the diagram -- tangible, premium, and strikingly real.",
     "4:3"),

    ("terminal_hacker", "Terminal Hacker", "Technical",
     "Take this whiteboard photograph and convert it into a diagram styled like a retro "
     "computer terminal display. " + CORE_INSTRUCTIONS + " "
     "Output the diagram on a pure black background. Use phosphor green (#00FF00) as the "
     "primary color for all text, lines, and shapes. Add a subtle CRT scan-line effect "
     "and slight screen curvature glow at the edges. Use a monospace terminal font for "
     "all text. Boxes should be drawn with ASCII-style borders. The result should look "
     "like output from a 1980s mainframe terminal -- minimal, technical, and unmistakably "
     "computer-native.",
     "4:3"),

    ("visionary", "Visionary Inspirational", "Technical",
     "Take this whiteboard photograph and convert it into a grand, visionary-style diagram "
     "that feels like a map of the future. " + CORE_INSTRUCTIONS + " "
     "Output the diagram on a deep space or cosmic gradient background (dark blues and "
     "purples with subtle star fields or nebula wisps). Render concepts as glowing nodes "
     "connected by luminous pathways of light. Use a palette of gold, white, and ethereal "
     "blue. Text should be clean and luminous, as if projected in light. Add subtle lens "
     "flare effects and soft radial glows around key concepts. The result should feel epic "
     "and aspirational -- like a strategic roadmap presented at a visionary keynote.",
     "16:9"),

    # --- Retro & Fun ---
    ("chalkboard", "Chalkboard", "Retro & Fun",
     "Take this whiteboard photograph and convert it into a diagram styled as if drawn on "
     "a classic green chalkboard. " + CORE_INSTRUCTIONS + " "
     "Output the diagram on a dark green chalkboard-textured background with subtle chalk "
     "dust. Use white and colored chalk (yellow, pink, light blue) for all lines, shapes, "
     "and text. The lettering should look like clean chalk handwriting. Add subtle smudge "
     "effects and chalk texture to lines. The result should feel like a beautifully "
     "organized lecture -- academic, warm, and intellectual.",
     "16:9"),

    ("psychedelic", "Eccentric Psychedelic", "Retro & Fun",
     "Take this whiteboard photograph and convert it into a wild, psychedelic-styled "
     "diagram bursting with color. " + CORE_INSTRUCTIONS + " "
     "Use intensely saturated, clashing colors -- electric purples, acid greens, hot "
     "magentas, deep oranges -- with swirling gradients and color bleeds between sections. "
     "Lines should pulse with energy, varying in thickness and color. Add organic, flowing "
     "patterns and mandala-like decorative fills inside shapes. Text should be bold and "
     "wavy, distorted slightly but still readable. The background should be a shifting "
     "kaleidoscope of color. The result should feel like a tech diagram dropped into a "
     "1960s concert poster -- overwhelming, hypnotic, and absolutely unforgettable.",
     "1:1"),

    ("mad_genius", "Mad Genius", "Retro & Fun",
     "Take this whiteboard photograph and convert it into a chaotic, sprawling "
     "mad-genius-style diagram. " + CORE_INSTRUCTIONS + " "
     "Output on a slightly yellowed, aged paper background with coffee stain marks and "
     "creased folds. Amplify the chaos -- make the handwriting more frantic and varied in "
     "size, add scribbled annotations in margins, underline things multiple times, circle "
     "key concepts aggressively, draw arrows that loop and cross over each other. Use red "
     "ink for emphatic corrections and blue ink for the main content. Scatter small "
     "doodles, question marks, and exclamation points in empty spaces. The result should "
     "look like the notebook of a brilliant but unhinged mind -- feverish, obsessive, and "
     "crackling with intellectual energy.",
     "auto"),

    ("retro_80s", "Retro 80s Synthwave", "Retro & Fun",
     "Take this whiteboard photograph and convert it into a retro 1980s synthwave-styled "
     "diagram. " + CORE_INSTRUCTIONS + " "
     "Output the diagram on a dark purple-to-black gradient background. Use hot pink, "
     "electric cyan, and neon yellow for lines, shapes, and text. Add subtle scan-line "
     "effects and a retro grid perspective floor fading into the background. Use a bold, "
     "blocky retro font for all labels. The result should feel like a tech diagram from an "
     "80s sci-fi movie -- glowing, vibrant, and unmistakably retro-futuristic.",
     "16:9"),

    ("woodcut", "Woodcut", "Retro & Fun",
     "Take this whiteboard photograph and convert it into a diagram styled as a medieval "
     "woodcut or linocut print. " + CORE_INSTRUCTIONS + " "
     "Output on an aged parchment or cream-colored background. Render all elements using "
     "bold black carved lines with visible wood-grain texture in the strokes. Use "
     "cross-hatching for shading and fills. Text should appear in a blackletter or "
     "old-style serif typeface. Shapes should have a rough, hand-carved quality. "
     "Optionally add a single spot color (a deep red or ochre) for emphasis on key "
     "elements. The result should look like a page from an illuminated technical "
     "manuscript -- ancient, authoritative, and delightfully absurd as a format for "
     "modern tech diagrams.",
     "auto"),

    # --- Language ---
    ("bilingual_hebrew", "Bilingual (Hebrew)", "Language",
     "Take this whiteboard photograph and convert it into a beautiful and polished "
     "bilingual diagram. " + CORE_INSTRUCTIONS + " "
     "Output only the diagram on a clean white background. Keep all existing English "
     "labels in place, and add Hebrew translations below or beside each label in a "
     "slightly smaller font. Hebrew text should read right-to-left and use clear, modern "
     "Hebrew typography. Use color coding to visually distinguish the two languages -- "
     "for example, dark grey for English and blue for Hebrew. The result should be a "
     "clean, professional bilingual diagram that is fully readable in both English and "
     "Hebrew.",
     "auto"),

    ("translated_hebrew", "Translated (Hebrew)", "Language",
     "Take this whiteboard photograph and convert it into a beautiful and polished diagram "
     "with all labels translated to Hebrew. " + CORE_INSTRUCTIONS + " "
     "Output only the diagram on a clean white background. Preserve all the original "
     "diagram structure, shapes, arrows, and layout -- but replace every English text "
     "label with its Hebrew translation. Hebrew text should read right-to-left and use "
     "clear, modern Hebrew typography. Ensure the translated labels fit naturally within "
     "their shapes and containers. Use clean, professional styling with colorful icons "
     "and clear visual hierarchy. The result should be a fully Hebrew-language version "
     "of the original diagram that reads naturally for a Hebrew speaker.",
     "auto"),
]

# Build lookup helpers
PRESET_BY_KEY = {p[0]: p for p in PROMPT_PRESETS}
PRESET_CATEGORIES = []
_seen_cats = set()
for p in PROMPT_PRESETS:
    if p[2] not in _seen_cats:
        PRESET_CATEGORIES.append(p[2])
        _seen_cats.add(p[2])

# Synchronous endpoint - returns results directly
FAL_SYNC_URL = "https://fal.run/fal-ai/nano-banana-2/edit"
# Queue endpoint - for fallback/polling
FAL_QUEUE_URL = "https://queue.fal.run/fal-ai/nano-banana-2/edit"

# --- Help content ---

HELP_HTML = """
<h2>Whiteboard Makeover - How to Use</h2>

<h3>Adding Images</h3>
<p>There are three ways to add whiteboard photos:</p>
<ul>
  <li><b>Drag and drop</b> files or folders directly onto the image area</li>
  <li><b>Add Images</b> button to browse and select individual files</li>
  <li><b>Add Folder</b> button to add all images from a directory</li>
</ul>
<p>Supported formats: PNG, JPG, JPEG, WebP, BMP</p>

<h3>Word Dictionary</h3>
<p><b>Double-click</b> any input image to open the Word Dictionary for that image.
This lets you tell the AI about specific words, names, or technical terms that appear
in your whiteboard. The AI will use these exact spellings instead of guessing.</p>
<p>Example: If your whiteboard mentions "Proxmox" or "Kubernetes", add those words
so they aren't misread as "Proxknox" or "Kubernites".</p>
<p>Images with dictionary words show a <b>[dict]</b> indicator.</p>

<h3>Style Presets</h3>
<p>Choose from 24+ built-in style presets across categories:</p>
<ul>
  <li><b>Professional</b> - Clean &amp; Polished, Corporate Clean, Minimalist Mono, etc.</li>
  <li><b>Creative</b> - Neon Sign, Comic Book, Pixel Art, Watercolor, etc.</li>
  <li><b>Technical</b> - Blueprint, Terminal Hacker, Dark Mode, etc.</li>
  <li><b>Retro &amp; Fun</b> - Chalkboard, Synthwave, Psychedelic, etc.</li>
  <li><b>Language</b> - Bilingual Hebrew, Translated Hebrew</li>
</ul>
<p>Each preset sets a recommended aspect ratio which you can override.</p>

<h3>Output Settings</h3>
<ul>
  <li><b>Format</b> - PNG, JPEG, or WebP</li>
  <li><b>Resolution</b> - 0.5K, 1K, 2K, or 4K</li>
  <li><b>Variants</b> - Generate 1-4 different outputs per input image</li>
  <li><b>Aspect Ratio</b> - Auto or a fixed ratio like 16:9, 4:3, etc.</li>
</ul>

<h3>Processing</h3>
<p>Click <b>Process</b> to start. An animated indicator shows progress for each image.
Processing typically takes 10-30 seconds per image depending on resolution.</p>
<p>Results are saved to a <b>processed/</b> subfolder next to the original images.</p>

<h3>Viewing Results</h3>
<p><b>Click any result thumbnail</b> to open an enlarged view. From the enlarged view
you can:</p>
<ul>
  <li><b>Send Back for Touchups</b> - re-process the original image (creates a new
  version like <code>_edited_v2</code>)</li>
  <li><b>Open in file manager</b> via the Open Output Folder button</li>
</ul>

<h3>CLI Mode</h3>
<p>Run from the command line for batch processing:</p>
<pre>whiteboard-makeover image1.jpg image2.jpg --preset blueprint
whiteboard-makeover folder/ --format webp --resolution 2K
whiteboard-makeover --list-presets</pre>
"""


def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
    else:
        cfg = {}
    if cfg.get("config_version", 0) < CONFIG_VERSION:
        cfg.setdefault("color", True)
        cfg.setdefault("handwritten", True)
        cfg["config_version"] = CONFIG_VERSION
        save_config(cfg)
    return cfg


def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def image_to_data_url(path: str) -> str:
    ext = Path(path).suffix.lower()
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "webp": "image/webp", "bmp": "image/bmp"}.get(ext.lstrip("."), "image/png")
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:{mime};base64,{b64}"


def call_fal_api(img_path: str, api_key: str, prompt: str,
                 output_format: str, resolution: str, num_images: int,
                 aspect_ratio: str = "auto") -> list[dict]:
    """Call Fal API. Try sync endpoint first, fall back to queue + polling."""
    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json",
    }
    data_url = image_to_data_url(img_path)
    payload = {
        "prompt": prompt,
        "image_urls": [data_url],
        "output_format": output_format,
        "resolution": resolution,
        "num_images": num_images,
    }
    if aspect_ratio and aspect_ratio != "auto":
        payload["aspect_ratio"] = aspect_ratio

    resp = requests.post(FAL_SYNC_URL, headers=headers, json=payload, timeout=300)
    resp.raise_for_status()
    result = resp.json()

    if "images" in result and result["images"]:
        return result["images"]

    request_id = result.get("request_id")
    if not request_id:
        return []

    result_url = f"{FAL_QUEUE_URL}/requests/{request_id}"
    status_url = f"{FAL_QUEUE_URL}/requests/{request_id}/status"

    for _ in range(120):
        time.sleep(2)
        status_resp = requests.get(status_url, headers=headers, timeout=30)
        status_resp.raise_for_status()
        status = status_resp.json()
        if status.get("status") == "COMPLETED":
            result_resp = requests.get(result_url, headers=headers, timeout=30)
            result_resp.raise_for_status()
            return result_resp.json().get("images", [])
        if status.get("status") in ("FAILED", "CANCELLED"):
            return []

    return []


class ProcessWorker(QThread):
    progress = pyqtSignal(int, int, str)
    image_started = pyqtSignal(str)
    image_saved = pyqtSignal(str, str)  # (output_path, source_path)
    finished = pyqtSignal(list)
    error = pyqtSignal(str, str)

    def __init__(self, image_paths, api_key, prompts, output_format, resolution,
                 num_images, aspect_ratio, output_suffixes=None):
        super().__init__()
        self.image_paths = image_paths
        self.api_key = api_key
        self.prompts = prompts
        self.output_format = output_format
        self.resolution = resolution
        self.num_images = num_images
        self.aspect_ratio = aspect_ratio
        self.output_suffixes = output_suffixes or [None] * len(image_paths)

    def run(self):
        total = len(self.image_paths)
        output_paths = []

        for i, img_path in enumerate(self.image_paths):
            p = Path(img_path)
            name = p.stem
            self.progress.emit(i, total, name)
            self.image_started.emit(img_path)

            try:
                images = call_fal_api(
                    img_path, self.api_key, self.prompts[i],
                    self.output_format, self.resolution, self.num_images,
                    self.aspect_ratio,
                )

                if not images:
                    self.error.emit(name, "No output image returned")
                    continue

                out_dir = p.parent / "processed"
                out_dir.mkdir(exist_ok=True)

                custom_suffix = self.output_suffixes[i]

                for j, img_data in enumerate(images):
                    img_url = img_data["url"]
                    img_resp = requests.get(img_url, timeout=60)
                    img_resp.raise_for_status()

                    if custom_suffix:
                        suffix = custom_suffix if len(images) == 1 else f"{custom_suffix}_{j + 1}"
                    else:
                        suffix = "_edited" if len(images) == 1 else f"_edited_{j + 1}"

                    out_path = out_dir / f"{name}{suffix}.{self.output_format}"
                    with open(out_path, "wb") as f:
                        f.write(img_resp.content)
                    output_paths.append(str(out_path))
                    self.image_saved.emit(str(out_path), img_path)

            except requests.exceptions.HTTPError as e:
                error_body = ""
                if e.response is not None:
                    try:
                        error_body = e.response.json().get("detail", e.response.text[:300])
                    except Exception:
                        error_body = e.response.text[:300]
                self.error.emit(name, str(error_body))
            except Exception as e:
                self.error.emit(name, str(e))

        self.progress.emit(total, total, "")
        self.finished.emit(output_paths)


class ClickableLabel(QLabel):
    """QLabel that emits a clicked signal."""
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


class DropListWidget(QListWidget):
    """QListWidget that accepts drag-and-drop of image files and folders, shown as thumbnails."""

    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setIconSize(QSize(100, 100))
        self.setSpacing(8)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setWrapping(True)
        self.setMovement(QListWidget.Movement.Static)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def _resolve_local_path(self, url):
        """Extract a local file path from a QUrl, with Wayland fallbacks."""
        local = url.toLocalFile()
        if local:
            return local
        raw = url.toString()
        if raw.startswith("file://"):
            return unquote(raw[7:])
        return None

    def dropEvent(self, event: QDropEvent):
        paths = []
        urls = event.mimeData().urls()
        if not urls and event.mimeData().hasText():
            # Some Wayland file managers send plain text URIs
            for line in event.mimeData().text().strip().splitlines():
                line = line.strip()
                if line.startswith("file://"):
                    local = unquote(line[7:])
                    p = Path(local)
                    if p.is_dir():
                        for f in sorted(p.iterdir()):
                            if f.suffix.lower() in IMAGE_EXTS and not f.stem.endswith("_edited"):
                                paths.append(str(f))
                    elif p.is_file() and p.suffix.lower() in IMAGE_EXTS:
                        paths.append(str(p))
        else:
            for url in urls:
                local = self._resolve_local_path(url)
                if not local:
                    continue
                p = Path(local)
                if p.is_dir():
                    for f in sorted(p.iterdir()):
                        if f.suffix.lower() in IMAGE_EXTS and not f.stem.endswith("_edited"):
                            paths.append(str(f))
                elif p.is_file() and p.suffix.lower() in IMAGE_EXTS:
                    paths.append(str(p))
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()

    def add_image(self, path: str, has_dict=False):
        """Add an image with a thumbnail icon."""
        pixmap = QPixmap(path)
        if pixmap.isNull():
            icon = QIcon()
        else:
            icon = QIcon(pixmap.scaled(
                100, 100,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        label = Path(path).name
        if has_dict:
            label += " [dict]"
        item = QListWidgetItem(icon, label)
        item.setSizeHint(QSize(120, 130))
        self.addItem(item)


class ApiKeyDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fal AI API Key")
        self.setFixedWidth(450)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Enter your Fal AI API key:"))
        hint = QLabel("Get one at fal.ai/dashboard/keys")
        hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(hint)

        self.entry = QLineEdit()
        self.entry.setEchoMode(QLineEdit.EchoMode.Password)
        self.entry.setPlaceholderText("fal-xxxxxxxxxxxxxxxx")
        layout.addWidget(self.entry)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_key(self):
        return self.entry.text().strip()


class SettingsDialog(QDialog):
    """Dialog for editing the custom prompt and API key."""

    def __init__(self, config_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(550)
        self.config_data = config_data

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # API key
        key_group = QGroupBox("API Key")
        key_layout = QVBoxLayout(key_group)
        self.key_entry = QLineEdit(config_data.get("api_key", ""))
        self.key_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_entry.setPlaceholderText("fal-xxxxxxxxxxxxxxxx")
        key_layout.addWidget(self.key_entry)
        hint = QLabel("Get one at fal.ai/dashboard/keys")
        hint.setStyleSheet("color: gray; font-size: 11px;")
        key_layout.addWidget(hint)
        layout.addWidget(key_group)

        # Custom prompt (used when preset is "Custom")
        prompt_group = QGroupBox("Custom Prompt")
        prompt_layout = QVBoxLayout(prompt_group)
        self.prompt_edit = QPlainTextEdit()
        default_preset = PROMPT_PRESETS[0]
        self.prompt_edit.setPlainText(config_data.get("custom_prompt", default_preset[3]))
        self.prompt_edit.setMaximumHeight(120)
        prompt_layout.addWidget(self.prompt_edit)

        reset_btn = QPushButton("Reset to Default")
        reset_btn.clicked.connect(lambda: self.prompt_edit.setPlainText(default_preset[3]))
        reset_row = QHBoxLayout()
        reset_row.addStretch()
        reset_row.addWidget(reset_btn)
        prompt_layout.addLayout(reset_row)
        layout.addWidget(prompt_group)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self):
        return {
            "api_key": self.key_entry.text().strip(),
            "custom_prompt": self.prompt_edit.toPlainText().strip(),
        }


class DictionaryDialog(QDialog):
    """Dialog for adding/removing words the AI should spell correctly."""

    def __init__(self, image_path, current_words=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Word Dictionary - {Path(image_path).name}")
        self.setMinimumWidth(420)
        self.setMinimumHeight(350)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        info = QLabel(
            "Add words, names, or technical terms that appear on this whiteboard. "
            "The AI will use these exact spellings instead of guessing."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(info)

        # Input row
        input_row = QHBoxLayout()
        self.word_entry = QLineEdit()
        self.word_entry.setPlaceholderText("Type a word and press Enter...")
        self.word_entry.returnPressed.connect(self._add_word)
        input_row.addWidget(self.word_entry)
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_word)
        input_row.addWidget(add_btn)
        layout.addLayout(input_row)

        # Word list
        self.word_list = QListWidget()
        self.word_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        if current_words:
            for w in current_words:
                self.word_list.addItem(w)
        layout.addWidget(self.word_list)

        # Remove button
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_selected)
        remove_row = QHBoxLayout()
        remove_row.addStretch()
        remove_row.addWidget(remove_btn)
        layout.addLayout(remove_row)

        # OK / Cancel
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add_word(self):
        word = self.word_entry.text().strip()
        if word:
            existing = [self.word_list.item(i).text() for i in range(self.word_list.count())]
            if word not in existing:
                self.word_list.addItem(word)
            self.word_entry.clear()

    def _remove_selected(self):
        for item in reversed(self.word_list.selectedItems()):
            self.word_list.takeItem(self.word_list.row(item))

    def get_words(self):
        return [self.word_list.item(i).text() for i in range(self.word_list.count())]


class ImageViewDialog(QDialog):
    """Full-size image viewer with touchup option."""

    touchup_requested = pyqtSignal(str)

    def __init__(self, image_path, source_path=None, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.source_path = source_path
        self.setWindowTitle(Path(image_path).name)
        self.setMinimumSize(600, 400)

        screen = self.screen().geometry() if self.screen() else None
        if screen:
            self.resize(int(screen.width() * 0.8), int(screen.height() * 0.8))
        else:
            self.resize(1200, 800)

        layout = QVBoxLayout(self)

        # Image in scroll area
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            max_w = self.width() - 40
            max_h = self.height() - 120
            self.image_label.setPixmap(pixmap.scaled(
                max_w, max_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        scroll = QScrollArea()
        scroll.setWidget(self.image_label)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        # Filename
        name_label = QLabel(Path(image_path).name)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("font-size: 12px; color: gray;")
        layout.addWidget(name_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        if source_path:
            touchup_btn = QPushButton("Send Back for Touchups")
            touchup_btn.clicked.connect(self._request_touchup)
            btn_row.addWidget(touchup_btn)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _request_touchup(self):
        self.touchup_requested.emit(self.image_path)
        self.accept()


class HelpDialog(QDialog):
    """How to Use dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("How to Use - Whiteboard Makeover")
        self.setMinimumSize(650, 520)

        layout = QVBoxLayout(self)
        text = QLabel(HELP_HTML)
        text.setWordWrap(True)
        text.setTextFormat(Qt.TextFormat.RichText)

        scroll = QScrollArea()
        scroll.setWidget(text)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Whiteboard Makeover")
        self.setMinimumSize(900, 600)
        self.resize(1050, 720)

        self.config_data = load_config()
        self.image_paths = []
        self.worker = None
        self._output_paths = []
        self._output_to_source = {}
        self._image_dictionaries = {}

        # Animation timer for processing status
        self._anim_timer = QTimer()
        self._anim_timer.timeout.connect(self._animate_status)
        self._anim_dots = 0
        self._anim_base_text = ""

        self._build_ui()
        self._build_menu()

        if not self.config_data.get("api_key"):
            QTimer.singleShot(300, self._open_settings)

    def _build_menu(self):
        menu = self.menuBar()
        file_menu = menu.addMenu("File")
        settings_action = QAction("Settings...", self)
        settings_action.triggered.connect(self._open_settings)
        file_menu.addAction(settings_action)
        file_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        help_menu = menu.addMenu("Help")
        how_to_action = QAction("How to Use", self)
        how_to_action.triggered.connect(self._show_help)
        help_menu.addAction(how_to_action)

    def _show_help(self):
        dialog = HelpDialog(self)
        dialog.exec()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("Whiteboard Makeover")
        font = title.font()
        font.setPointSize(18)
        font.setBold(True)
        title.setFont(font)
        root.addWidget(title)

        # Main content
        content = QHBoxLayout()
        content.setSpacing(12)

        # Left: image list with drag-and-drop thumbnails
        img_group = QGroupBox("Images (drag and drop files or folders here)")
        img_layout = QVBoxLayout(img_group)

        self.image_list = DropListWidget()
        self.image_list.files_dropped.connect(self._on_files_dropped)
        self.image_list.itemDoubleClicked.connect(self._open_dictionary)
        img_layout.addWidget(self.image_list)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        for label, slot in [("Add Images", self._add_images),
                            ("Add Folder", self._add_folder),
                            ("Remove Selected", self._remove_selected),
                            ("Clear All", self._clear_all)]:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            btn_row.addWidget(btn)
        btn_row.addStretch()
        img_layout.addLayout(btn_row)

        dict_hint = QLabel("Double-click an image to add a word dictionary")
        dict_hint.setStyleSheet("color: gray; font-size: 10px;")
        img_layout.addWidget(dict_hint)

        content.addWidget(img_group, stretch=3)

        # Right: options
        right = QVBoxLayout()
        right.setSpacing(12)

        # Preset selector
        preset_group = QGroupBox("Style Preset")
        preset_layout = QVBoxLayout(preset_group)

        self.preset_combo = QComboBox()
        saved_preset = self.config_data.get("preset", "clean_polished")
        idx = 0
        current_idx = 0
        for cat in PRESET_CATEGORIES:
            self.preset_combo.addItem(f"--- {cat} ---")
            model = self.preset_combo.model()
            item = model.item(idx)
            item.setEnabled(False)
            idx += 1
            for p in PROMPT_PRESETS:
                if p[2] == cat:
                    self.preset_combo.addItem(f"  {p[1]}", userData=p[0])
                    if p[0] == saved_preset:
                        current_idx = idx
                    idx += 1
        # Add Custom at the end
        self.preset_combo.addItem("--- Custom ---")
        model = self.preset_combo.model()
        model.item(idx).setEnabled(False)
        idx += 1
        self.preset_combo.addItem("  Custom Prompt", userData="custom")
        if saved_preset == "custom":
            current_idx = idx
        self.preset_combo.setCurrentIndex(current_idx)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        preset_layout.addWidget(self.preset_combo)

        self.preset_desc = QLabel("")
        self.preset_desc.setWordWrap(True)
        self.preset_desc.setStyleSheet("color: gray; font-size: 11px;")
        self.preset_desc.setMaximumHeight(40)
        preset_layout.addWidget(self.preset_desc)
        self._update_preset_desc()

        right.addWidget(preset_group)

        # Output settings
        output_group = QGroupBox("Output")
        output_form = QFormLayout(output_group)
        output_form.setSpacing(8)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["png", "jpeg", "webp"])
        self.format_combo.setCurrentText(self.config_data.get("output_format", "png"))
        output_form.addRow("Format:", self.format_combo)

        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["0.5K", "1K", "2K", "4K"])
        self.resolution_combo.setCurrentText(self.config_data.get("resolution", "1K"))
        output_form.addRow("Resolution:", self.resolution_combo)

        self.num_images_spin = QSpinBox()
        self.num_images_spin.setRange(1, 4)
        self.num_images_spin.setValue(self.config_data.get("num_images", 1))
        output_form.addRow("Variants (per input):", self.num_images_spin)

        right.addWidget(output_group)

        # Aspect ratio buttons
        ar_group = QGroupBox("Aspect Ratio")
        ar_layout = QVBoxLayout(ar_group)
        ar_row1 = QHBoxLayout()
        ar_row2 = QHBoxLayout()
        self.ar_buttons = {}
        saved_ar = self.config_data.get("aspect_ratio", "auto")
        for i, ar in enumerate(ASPECT_RATIOS):
            btn = QPushButton(ar)
            btn.setCheckable(True)
            btn.setChecked(ar == saved_ar)
            btn.setMinimumWidth(50)
            btn.clicked.connect(lambda checked, a=ar: self._select_aspect_ratio(a))
            self.ar_buttons[ar] = btn
            if i < 5:
                ar_row1.addWidget(btn)
            else:
                ar_row2.addWidget(btn)
        ar_layout.addLayout(ar_row1)
        ar_layout.addLayout(ar_row2)
        right.addWidget(ar_group)

        info_label = QLabel("Outputs saved to processed/ subfolder.")
        info_label.setStyleSheet("color: gray; font-size: 11px;")
        right.addWidget(info_label)

        right.addStretch()
        content.addLayout(right, stretch=1)
        root.addLayout(content)

        # Bottom
        bottom = QHBoxLayout()
        bottom.setSpacing(12)

        self.process_btn = QPushButton("Process")
        font = self.process_btn.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 1)
        self.process_btn.setFont(font)
        self.process_btn.clicked.connect(self._start_processing)
        bottom.addWidget(self.process_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        bottom.addWidget(self.progress_bar, stretch=1)

        self.status_label = QLabel("Ready")
        self.status_label.setMinimumWidth(220)
        bottom.addWidget(self.status_label)

        root.addLayout(bottom)

        # Results area
        self.results_group = QGroupBox("Results (click to enlarge)")
        results_layout = QVBoxLayout(self.results_group)

        self.results_scroll = QScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.setMinimumHeight(140)
        self.results_scroll.setMaximumHeight(180)
        self.results_container = QWidget()
        self.results_thumb_layout = QHBoxLayout(self.results_container)
        self.results_thumb_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.results_thumb_layout.setSpacing(8)
        self.results_scroll.setWidget(self.results_container)
        results_layout.addWidget(self.results_scroll)

        results_btn_row = QHBoxLayout()
        results_btn_row.addStretch()
        self.new_job_btn = QPushButton("New Job")
        self.new_job_btn.clicked.connect(self._new_job)
        results_btn_row.addWidget(self.new_job_btn)
        self.open_folder_btn = QPushButton("Open Output Folder")
        self.open_folder_btn.clicked.connect(self._open_output_folder)
        results_btn_row.addWidget(self.open_folder_btn)
        results_layout.addLayout(results_btn_row)

        self.results_group.setVisible(False)
        root.addWidget(self.results_group)

        self._last_output_dir = None

    # --- Aspect ratio ---

    def _select_aspect_ratio(self, ratio):
        for ar, btn in self.ar_buttons.items():
            btn.setChecked(ar == ratio)

    def _get_selected_aspect_ratio(self):
        for ar, btn in self.ar_buttons.items():
            if btn.isChecked():
                return ar
        return "auto"

    # --- Preset ---

    def _on_preset_changed(self, index):
        self._update_preset_desc()
        key = self.preset_combo.currentData()
        if key and key != "custom" and key in PRESET_BY_KEY:
            default_ar = PRESET_BY_KEY[key][4]
            self._select_aspect_ratio(default_ar)

    def _update_preset_desc(self):
        key = self.preset_combo.currentData()
        if key and key != "custom" and key in PRESET_BY_KEY:
            preset = PRESET_BY_KEY[key]
            self.preset_desc.setText(f"Category: {preset[2]}  |  Default ratio: {preset[4]}")
        elif key == "custom":
            self.preset_desc.setText("Uses your custom prompt from Settings.")
        else:
            self.preset_desc.setText("")

    def _get_active_prompt(self):
        key = self.preset_combo.currentData()
        if key and key != "custom" and key in PRESET_BY_KEY:
            return PRESET_BY_KEY[key][3]
        return self.config_data.get("custom_prompt", PROMPT_PRESETS[0][3])

    # --- Animation ---

    def _animate_status(self):
        self._anim_dots = (self._anim_dots + 1) % 4
        dots = "." * (self._anim_dots + 1)
        self.status_label.setText(f"{self._anim_base_text}{dots}")

    # --- File/folder actions ---

    def _open_output_folder(self):
        if self._last_output_dir and Path(self._last_output_dir).is_dir():
            subprocess.Popen(["xdg-open", self._last_output_dir])

    def _new_job(self):
        self._clear_results()
        self.results_group.setVisible(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("Ready")

    def _clear_results(self):
        while self.results_thumb_layout.count():
            item = self.results_thumb_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._output_paths.clear()
        self._output_to_source.clear()

    def _open_settings(self):
        dialog = SettingsDialog(self.config_data, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            vals = dialog.get_values()
            if vals["api_key"]:
                self.config_data["api_key"] = vals["api_key"]
            if vals["custom_prompt"]:
                self.config_data["custom_prompt"] = vals["custom_prompt"]
            save_config(self.config_data)
            self.status_label.setText("Settings saved")

    def _on_files_dropped(self, paths):
        for p in paths:
            if p not in self.image_paths:
                self.image_paths.append(p)
                has_dict = p in self._image_dictionaries and bool(self._image_dictionaries[p])
                self.image_list.add_image(p, has_dict=has_dict)

    def _add_images(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select whiteboard images", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All files (*)")
        for p in paths:
            if p not in self.image_paths:
                self.image_paths.append(p)
                self.image_list.add_image(p)

    def _add_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Select folder with images")
        if d:
            folder = Path(d)
            for f in sorted(folder.iterdir()):
                fp = str(f)
                if f.suffix.lower() in IMAGE_EXTS and not f.stem.endswith("_edited") and fp not in self.image_paths:
                    self.image_paths.append(fp)
                    self.image_list.add_image(fp)

    def _remove_selected(self):
        for item in reversed(self.image_list.selectedItems()):
            idx = self.image_list.row(item)
            self.image_list.takeItem(idx)
            removed = self.image_paths.pop(idx)
            self._image_dictionaries.pop(removed, None)

    def _clear_all(self):
        self.image_list.clear()
        self.image_paths.clear()
        self._image_dictionaries.clear()

    # --- Dictionary ---

    def _open_dictionary(self, item):
        idx = self.image_list.row(item)
        if idx < 0 or idx >= len(self.image_paths):
            return
        path = self.image_paths[idx]
        current = self._image_dictionaries.get(path, [])
        dialog = DictionaryDialog(path, current, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            words = dialog.get_words()
            if words:
                self._image_dictionaries[path] = words
            elif path in self._image_dictionaries:
                del self._image_dictionaries[path]
            label = Path(path).name
            if words:
                label += " [dict]"
            item.setText(label)

    # --- Processing ---

    def _build_prompts(self):
        """Build a per-image prompt list, injecting dictionary words where present."""
        base_prompt = self._get_active_prompt()
        prompts = []
        for img_path in self.image_paths:
            words = self._image_dictionaries.get(img_path, [])
            if words:
                word_list = ", ".join(words)
                prompt = (
                    base_prompt +
                    f"\n\nThe following specific terms appear in this whiteboard and "
                    f"should be spelled exactly as listed: {word_list}"
                )
            else:
                prompt = base_prompt
            prompts.append(prompt)
        return prompts

    def _start_processing(self):
        if self.worker and self.worker.isRunning():
            return
        if not self.config_data.get("api_key"):
            self._open_settings()
            if not self.config_data.get("api_key"):
                return
        if not self.image_paths:
            QMessageBox.warning(self, "No images", "Add at least one image first.")
            return

        # Save current UI state
        preset_key = self.preset_combo.currentData() or "clean_polished"
        self.config_data["preset"] = preset_key
        self.config_data["output_format"] = self.format_combo.currentText()
        self.config_data["resolution"] = self.resolution_combo.currentText()
        self.config_data["num_images"] = self.num_images_spin.value()
        self.config_data["aspect_ratio"] = self._get_selected_aspect_ratio()
        save_config(self.config_data)

        # Clear previous results and show results area
        self._clear_results()
        self.results_group.setVisible(True)

        self.process_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(len(self.image_paths))

        # Start animation
        self._anim_base_text = "Working on it"
        self._anim_dots = 0
        self._anim_timer.start(400)

        prompts = self._build_prompts()

        self.worker = ProcessWorker(
            list(self.image_paths),
            self.config_data["api_key"],
            prompts,
            self.config_data.get("output_format", "png"),
            self.config_data.get("resolution", "1K"),
            self.config_data.get("num_images", 1),
            self._get_selected_aspect_ratio(),
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.image_saved.connect(self._on_image_saved)
        self.worker.error.connect(self._on_error)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, current, total, name):
        self.progress_bar.setValue(current)
        if name:
            self._anim_base_text = f"Working on {current + 1}/{total}: {name}"
            self._anim_dots = 0

    def _on_image_saved(self, path, source_path):
        """Show each output thumbnail live as it arrives."""
        self._output_paths.append(path)
        self._output_to_source[path] = source_path
        self._last_output_dir = str(Path(path).parent)
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            thumb = ClickableLabel()
            thumb.setCursor(Qt.CursorShape.PointingHandCursor)
            thumb.setPixmap(pixmap.scaled(
                120, 120,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
            thumb.setToolTip(f"{Path(path).name} (click to enlarge)")
            thumb.setStyleSheet("border: 1px solid #ccc; padding: 2px;")
            thumb.clicked.connect(lambda p=path: self._show_enlarged(p))
            self.results_thumb_layout.addWidget(thumb)

    def _show_enlarged(self, output_path):
        source = self._output_to_source.get(output_path)
        dialog = ImageViewDialog(output_path, source_path=source, parent=self)
        dialog.touchup_requested.connect(self._touchup_image)
        dialog.exec()

    def _touchup_image(self, output_path):
        """Re-process the original source image with a versioned suffix."""
        source_path = self._output_to_source.get(output_path)
        if not source_path:
            QMessageBox.warning(self, "Error", "Original source image not found.")
            return

        stem = Path(source_path).stem
        out_dir = Path(source_path).parent / "processed"
        fmt = self.format_combo.currentText()
        version = 2
        while (out_dir / f"{stem}_edited_v{version}.{fmt}").exists():
            version += 1
        suffix = f"_edited_v{version}"

        # Build prompt with dictionary if set
        base_prompt = self._get_active_prompt()
        words = self._image_dictionaries.get(source_path, [])
        if words:
            word_list = ", ".join(words)
            prompt = (
                base_prompt +
                f"\n\nThe following specific terms appear in this whiteboard and "
                f"should be spelled exactly as listed: {word_list}"
            )
        else:
            prompt = base_prompt

        self.process_btn.setEnabled(False)
        self._anim_base_text = f"Touchup: {Path(source_path).name}"
        self._anim_dots = 0
        self._anim_timer.start(400)
        self.progress_bar.setMaximum(1)
        self.progress_bar.setValue(0)

        self.worker = ProcessWorker(
            [source_path],
            self.config_data["api_key"],
            [prompt],
            fmt,
            self.config_data.get("resolution", "1K"),
            self.config_data.get("num_images", 1),
            self._get_selected_aspect_ratio(),
            output_suffixes=[suffix],
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.image_saved.connect(self._on_image_saved)
        self.worker.error.connect(self._on_error)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_error(self, name, error_msg):
        QMessageBox.critical(self, "Error", f"Failed to process {name}:\n{error_msg}")

    def _on_finished(self, output_paths):
        self._anim_timer.stop()
        self.process_btn.setEnabled(True)
        count = len(output_paths)
        self.status_label.setText(f"Done! {count} output(s) saved.")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
