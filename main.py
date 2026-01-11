from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict

import os
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

# ---------------- OPTIONAL LIBS ----------------

try:
    import piexif  # type: ignore
    HAS_PIEXIF = True
except Exception:
    piexif = None
    HAS_PIEXIF = False

try:
    from iptcinfo3 import IPTCInfo  # type: ignore
    HAS_IPTC = True
except Exception:
    IPTCInfo = None
    HAS_IPTC = False

try:
    from libxmp import XMPFiles  # type: ignore
    HAS_XMP = True
except Exception:
    XMPFiles = None
    HAS_XMP = False

try:
    from c2pa.c2pa import Reader  # type: ignore
    HAS_C2PA = True
except Exception:
    Reader = None
    HAS_C2PA = False


# =========================================================
# SAVE HELPER (FIXED)
# =========================================================

def save_image_safely(img: Image.Image, out_path: str, jpg_bg=(255, 255, 255)) -> None:
    """
    Save an image to out_path handling format quirks (e.g. RGBA -> JPEG).
    - If saving as JPEG and image has alpha, composite on a background first.
    """
    ext = Path(out_path).suffix.lower()
    is_jpeg = ext in (".jpg", ".jpeg")

    if is_jpeg:
        # JPEG doesn't support alpha -> ensure RGB
        if img.mode in ("RGBA", "LA"):
            bg = Image.new("RGB", img.size, jpg_bg)
            alpha = img.split()[-1]
            bg.paste(img.convert("RGB"), mask=alpha)
            img = bg
        elif img.mode == "P":
            # Palette images can have transparency
            rgba = img.convert("RGBA")
            bg = Image.new("RGB", rgba.size, jpg_bg)
            alpha = rgba.split()[-1]
            bg.paste(rgba.convert("RGB"), mask=alpha)
            img = bg
        else:
            img = img.convert("RGB")

        img.save(out_path, format="JPEG", quality=95, optimize=True, progressive=True)
        return

    # Other formats (PNG/WebP/...) -> save normally (keeps alpha if supported)
    img.save(out_path)


# =========================================================
# METADATA DETECTION
# =========================================================

def detect_exif(path: str) -> Dict[str, bool]:
    """
    Returns:
    {
        "present": bool,
        "strong_camera": bool
    }

    strong_camera=True only when Make + Model + DateTimeOriginal exist.
    This avoids classifying converted/exported JPEGs as "real camera" photos.
    """
    if not HAS_PIEXIF or piexif is None:
        return {"present": False, "strong_camera": False}

    try:
        meta = piexif.load(path)
        zeroth = meta.get("0th", {}) or {}
        exif = meta.get("Exif", {}) or {}
        gps = meta.get("GPS", {}) or {}

        present = any(
            isinstance(meta.get(k, {}), dict) and len(meta.get(k, {})) > 0
            for k in ("0th", "Exif", "GPS", "1st", "Interop")
        ) or bool(meta.get("thumbnail"))

        make = zeroth.get(piexif.ImageIFD.Make)
        model = zeroth.get(piexif.ImageIFD.Model)
        dt = exif.get(piexif.ExifIFD.DateTimeOriginal) or zeroth.get(piexif.ImageIFD.DateTime)

        def _has_value(x) -> bool:
            if x is None:
                return False
            if isinstance(x, bytes):
                return len(x.strip()) > 0
            if isinstance(x, str):
                return len(x.strip()) > 0
            return True

        strong_camera = _has_value(make) and _has_value(model) and _has_value(dt)
        _ = gps  # kept for future expansion

        return {"present": bool(present), "strong_camera": bool(strong_camera)}
    except Exception:
        return {"present": False, "strong_camera": False}


def detect_iptc(path: str) -> bool:
    """
    IPTC (IIM) best-effort via iptcinfo3.
    """
    if not HAS_IPTC or IPTCInfo is None:
        return False

    try:
        info = IPTCInfo(path, force=True)

        for attr in ("data", "_data"):
            d = getattr(info, attr, None)
            if isinstance(d, dict) and any(v not in (None, b"", "", [], ()) for v in d.values()):
                return True

        dct = getattr(info, "__dict__", {}) or {}
        if any(v not in (None, b"", "", [], ()) for v in dct.values()):
            return True

        return False
    except Exception:
        return False


def detect_xmp(path: str) -> bool:
    """
    XMP via python-xmp-toolkit (libxmp).
    """
    if not HAS_XMP or XMPFiles is None:
        return False

    xf = None
    try:
        xf = XMPFiles(file_path=path)
        xmp = xf.get_xmp()
        return xmp is not None
    except Exception:
        return False
    finally:
        try:
            if xf is not None:
                xf.close_file()
        except Exception:
            pass


def detect_c2pa(path: str) -> str:
    """
    returns: "yes" | "maybe" | "no"
    Uses c2pa-python when available, otherwise a conservative heuristic.
    """
    if HAS_C2PA and Reader is not None:
        try:
            r = Reader(path)

            store = None
            if hasattr(r, "get_manifest_store"):
                store = r.get_manifest_store()
            elif hasattr(r, "manifest_store"):
                store = r.manifest_store

            if store:
                return "yes"
        except Exception:
            pass

    try:
        data = Path(path).read_bytes().lower()
        if b"jumb" in data or b"urn:c2pa:" in data or b"contentcredentials" in data:
            return "maybe"
    except Exception:
        pass

    return "no"


# =========================================================
# AI LIKELIHOOD SUMMARY + BADGE
# =========================================================

def summarize_ai_likelihood(
    exif_present: bool,
    strong_camera_exif: bool,
    iptc: bool,
    xmp: bool,
    c2pa: str
) -> Dict[str, str]:

    if c2pa == "yes":
        return {
            "level": "high",
            "color": "#c0392b",
            "text": (
                "This image contains Content Credentials (C2PA).\n"
                "It was likely generated or modified using AI-based tools."
            )
        }

    if c2pa == "maybe":
        return {
            "level": "medium",
            "color": "#f1c40f",
            "text": (
                "This image shows partial Content Credentials signals.\n"
                "It may have been generated or modified using AI-based tools."
            )
        }

    if exif_present and not strong_camera_exif:
        return {
            "level": "medium",
            "color": "#f1c40f",
            "text": (
                "This image contains generic metadata but no coherent camera information.\n"
                "It may have been generated or modified using software, including AI."
            )
        }

    if exif_present and strong_camera_exif:
        return {
            "level": "low",
            "color": "#27ae60",
            "text": (
                "This image contains coherent camera metadata.\n"
                "There are no metadata-based indications that it was generated by AI."
            )
        }

    if xmp or iptc:
        return {
            "level": "medium",
            "color": "#f1c40f",
            "text": (
                "This image contains editing metadata but no camera information.\n"
                "It may have been generated or modified using software, including AI."
            )
        }

    return {
        "level": "unknown",
        "color": "#7f8c8d",
        "text": (
            "This image does not contain meaningful metadata.\n"
            "It is not possible to determine whether it was generated by AI based on metadata alone."
        )
    }


# =========================================================
# GUI APPLICATION
# =========================================================

class MetadataRemoverApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Image Metadata Inspector & Cleaner")
        self.root.geometry("900x600")

        self.image_path: Optional[str] = None
        self.original_image: Optional[Image.Image] = None
        self.clean_image: Optional[Image.Image] = None

        self._build_ui()

    def _build_ui(self):
        main = tk.Frame(self.root, padx=10, pady=10)
        main.pack(expand=True, fill=tk.BOTH)

        top = tk.Frame(main)
        top.pack(fill=tk.X)

        tk.Button(top, text="Upload Image", command=self.upload_image).pack(side=tk.LEFT)
        self.run_btn = tk.Button(top, text="Run", state=tk.DISABLED, command=self.process_image)
        self.run_btn.pack(side=tk.LEFT, padx=5)
        self.save_btn = tk.Button(top, text="Download", state=tk.DISABLED, command=self.download_image)
        self.save_btn.pack(side=tk.LEFT)

        content = tk.Frame(main)
        content.pack(expand=True, fill=tk.BOTH, pady=10)

        self.preview = tk.Label(content, bg="#ddd", text="Upload an image")
        self.preview.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=(0, 10))

        side = tk.Frame(content, width=340, bd=1, relief=tk.SUNKEN)
        side.pack(side=tk.RIGHT, fill=tk.Y)
        side.pack_propagate(False)

        tk.Label(side, text="Metadata detected", font=("Helvetica", 12, "bold")).pack(pady=(10, 6))

        self.meta_vars = {
            "EXIF": tk.BooleanVar(),
            "IPTC": tk.BooleanVar(),
            "XMP": tk.BooleanVar(),
            "C2PA": tk.BooleanVar(),
        }

        for k, v in self.meta_vars.items():
            tk.Checkbutton(side, text=k, variable=v, state=tk.DISABLED).pack(anchor="w", padx=12)

        tk.Label(side, text="AI Likelihood", font=("Helvetica", 12, "bold")).pack(pady=(14, 6))

        self.badge = tk.Label(
            side,
            text="—",
            fg="white",
            bg="#7f8c8d",
            font=("Helvetica", 10, "bold"),
            padx=10,
            pady=5
        )
        self.badge.pack(padx=12, pady=(0, 10), fill=tk.X)

        tk.Label(side, text="Additional Info", font=("Helvetica", 12, "bold")).pack(pady=(10, 6))

        self.additional_info = tk.Text(side, height=10, wrap="word", state=tk.DISABLED)
        self.additional_info.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        self.status = tk.Label(main, text="Ready", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

    def _set_additional_info(self, text: str):
        self.additional_info.config(state=tk.NORMAL)
        self.additional_info.delete("1.0", tk.END)
        self.additional_info.insert(tk.END, text)
        self.additional_info.config(state=tk.DISABLED)

    def upload_image(self):
        path = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp")]
        )
        if not path:
            return

        try:
            self.image_path = path
            self.original_image = Image.open(path)

            thumb = self.original_image.copy()
            thumb.thumbnail((500, 500))
            self.tk_img = ImageTk.PhotoImage(thumb)
            self.preview.config(image=self.tk_img, text="")

            self.run_btn.config(state=tk.NORMAL)
            self.save_btn.config(state=tk.DISABLED)
            self.clean_image = None

            self.detect_metadata()
            self.status.config(text=f"Loaded: {os.path.basename(path)}")

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def detect_metadata(self):
        if not self.image_path:
            return

        exif_res = detect_exif(self.image_path)
        exif_present = exif_res["present"]
        strong_camera = exif_res["strong_camera"]

        iptc_present = detect_iptc(self.image_path)
        xmp_present = detect_xmp(self.image_path)
        c2pa_status = detect_c2pa(self.image_path)

        self.meta_vars["EXIF"].set(exif_present)
        self.meta_vars["IPTC"].set(iptc_present)
        self.meta_vars["XMP"].set(xmp_present)
        self.meta_vars["C2PA"].set(c2pa_status in ("yes", "maybe"))

        summary = summarize_ai_likelihood(
            exif_present=exif_present,
            strong_camera_exif=strong_camera,
            iptc=iptc_present,
            xmp=xmp_present,
            c2pa=c2pa_status
        )

        self.badge.config(text=summary["level"].upper(), bg=summary["color"])
        self._set_additional_info(summary["text"])

    def process_image(self):
        if not self.original_image:
            return
        self.clean_image = Image.frombytes(
            self.original_image.mode,
            self.original_image.size,
            self.original_image.tobytes()
        )
        self.save_btn.config(state=tk.NORMAL)
        self.status.config(text="Processed: pixel-only copy created.")

    def download_image(self):
        if not self.clean_image or not self.image_path:
            return

        base, _ = os.path.splitext(os.path.basename(self.image_path))

        out = filedialog.asksaveasfilename(
            initialfile=f"{base}_clean.jpg",
            defaultextension=".jpg",
            filetypes=[
                ("JPEG", "*.jpg;*.jpeg"),
                ("PNG", "*.png"),
                ("WebP", "*.webp"),
            ],
        )
        if not out:
            return

        try:
            save_image_safely(self.clean_image, out, jpg_bg=(255, 255, 255))
            self.status.config(text=f"Saved: {os.path.basename(out)}")
        except Exception as e:
            messagebox.showerror("Save error", str(e))


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    root = tk.Tk()
    MetadataRemoverApp(root)
    root.mainloop()
