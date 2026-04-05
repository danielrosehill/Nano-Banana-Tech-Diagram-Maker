#!/usr/bin/env python3
"""Nano Whiteboard Doctor - Clean up whiteboard photos with Fal AI Nano Banana 2."""

import base64
import json
import subprocess
import sys
import time
from pathlib import Path

import requests
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QAction, QDragEnterEvent, QDropEvent, QPixmap, QIcon
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

CONFIG_DIR = Path.home() / ".config" / "nano-whiteboard-doctor"
CONFIG_FILE = CONFIG_DIR / "config.json"
CONFIG_VERSION = 2  # bump to force default migration

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


def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
    else:
        cfg = {}
    # Migrate old configs that lack version
    if cfg.get("config_version", 0) < CONFIG_VERSION:
        cfg.setdefault("color", True)
        cfg.setdefault("handwritten", True)
        if cfg.get("color") is False and "config_version" not in cfg:
            cfg["color"] = True
        if cfg.get("handwritten") is False and "config_version" not in cfg:
            cfg["handwritten"] = True
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

    # Try synchronous endpoint first
    resp = requests.post(FAL_SYNC_URL, headers=headers, json=payload, timeout=300)
    resp.raise_for_status()
    result = resp.json()

    # If we got images directly, return them
    if "images" in result and result["images"]:
        return result["images"]

    # If we got a queue response, poll for result
    request_id = result.get("request_id")
    if not request_id:
        return []

    result_url = f"{FAL_QUEUE_URL}/requests/{request_id}"
    status_url = f"{FAL_QUEUE_URL}/requests/{request_id}/status"

    for _ in range(120):  # up to ~4 minutes
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
    image_saved = pyqtSignal(str)  # emitted per output file for live thumbnails
    finished = pyqtSignal(list)  # list of output file paths
    error = pyqtSignal(str, str)

    def __init__(self, image_paths, api_key, prompt, output_format, resolution,
                 num_images, aspect_ratio):
        super().__init__()
        self.image_paths = image_paths
        self.api_key = api_key
        self.prompt = prompt
        self.output_format = output_format
        self.resolution = resolution
        self.num_images = num_images
        self.aspect_ratio = aspect_ratio

    def run(self):
        total = len(self.image_paths)
        output_paths = []

        for i, img_path in enumerate(self.image_paths):
            p = Path(img_path)
            name = p.stem
            self.progress.emit(i, total, name)

            try:
                images = call_fal_api(
                    img_path, self.api_key, self.prompt,
                    self.output_format, self.resolution, self.num_images,
                    self.aspect_ratio,
                )

                if not images:
                    self.error.emit(name, "No output image returned")
                    continue

                # Save to processed/ subfolder
                out_dir = p.parent / "processed"
                out_dir.mkdir(exist_ok=True)

                for j, img_data in enumerate(images):
                    img_url = img_data["url"]
                    img_resp = requests.get(img_url, timeout=60)
                    img_resp.raise_for_status()

                    suffix = "_edited" if len(images) == 1 else f"_edited_{j + 1}"
                    out_path = out_dir / f"{name}{suffix}.{self.output_format}"
                    with open(out_path, "wb") as f:
                        f.write(img_resp.content)
                    output_paths.append(str(out_path))
                    self.image_saved.emit(str(out_path))

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
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent):
        paths = []
        for url in event.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.is_dir():
                for f in sorted(p.iterdir()):
                    if f.suffix.lower() in IMAGE_EXTS and not f.stem.endswith("_edited"):
                        paths.append(str(f))
            elif p.is_file() and p.suffix.lower() in IMAGE_EXTS:
                paths.append(str(p))
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()

    def add_image(self, path: str):
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
        item = QListWidgetItem(icon, Path(path).name)
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nano Whiteboard Doctor")
        self.setMinimumSize(900, 600)
        self.resize(1050, 720)

        self.config_data = load_config()
        self.image_paths = []
        self.worker = None
        self._output_paths = []

        self._build_ui()
        self._build_menu()

        if not self.config_data.get("api_key"):
            QTimer.singleShot(300, self._open_settings)

    def _build_menu(self):
        menu = self.menuBar()
        settings_menu = menu.addMenu("File")
        settings_action = QAction("Settings...", self)
        settings_action.triggered.connect(self._open_settings)
        settings_menu.addAction(settings_action)
        settings_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        settings_menu.addAction(quit_action)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("Nano Whiteboard Doctor")
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
            # Make category headers non-selectable
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
        bottom.addWidget(self.status_label)

        root.addLayout(bottom)

        # Results area (live thumbnails + open folder + new job)
        self.results_group = QGroupBox("Results")
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

    def _select_aspect_ratio(self, ratio):
        for ar, btn in self.ar_buttons.items():
            btn.setChecked(ar == ratio)

    def _get_selected_aspect_ratio(self):
        for ar, btn in self.ar_buttons.items():
            if btn.isChecked():
                return ar
        return "auto"

    def _on_preset_changed(self, index):
        self._update_preset_desc()
        # Update aspect ratio to preset default
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

    def _open_output_folder(self):
        if self._last_output_dir and Path(self._last_output_dir).is_dir():
            subprocess.Popen(["xdg-open", self._last_output_dir])

    def _new_job(self):
        """Clear results and reset for a new batch."""
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
                self.image_list.add_image(p)

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
            self.image_paths.pop(idx)

    def _clear_all(self):
        self.image_list.clear()
        self.image_paths.clear()

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

        self.worker = ProcessWorker(
            list(self.image_paths),
            self.config_data["api_key"],
            self._get_active_prompt(),
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
            self.status_label.setText(f"Processing {current + 1}/{total}: {name}")

    def _on_image_saved(self, path):
        """Show each output thumbnail live as it arrives."""
        self._output_paths.append(path)
        self._last_output_dir = str(Path(path).parent)
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            thumb = QLabel()
            thumb.setPixmap(pixmap.scaled(
                120, 120,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
            thumb.setToolTip(Path(path).name)
            thumb.setStyleSheet("border: 1px solid #ccc; padding: 2px;")
            self.results_thumb_layout.addWidget(thumb)

    def _on_error(self, name, error_msg):
        QMessageBox.critical(self, "Error", f"Failed to process {name}:\n{error_msg}")

    def _on_finished(self, output_paths):
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
