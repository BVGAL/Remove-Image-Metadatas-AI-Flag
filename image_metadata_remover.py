from __future__ import annotations
from pathlib import Path
from typing import Union, Dict, Any, List, Tuple

import os
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk


# =========================================================
# C2PA DETECTION UTILITIES
# =========================================================

def _parse_jpeg_segments(data: bytes) -> List[Tuple[int, bytes]]:
    """Parse JPEG segments and return (marker, payload)."""
    if len(data) < 4 or data[:2] != b"\xFF\xD8":
        return []

    segments = []
    i = 2
    n = len(data)

    while i + 4 <= n:
        if data[i] != 0xFF:
            i += 1
            continue
        while i < n and data[i] == 0xFF:
            i += 1
        if i >= n:
            break

        marker = data[i]
        i += 1

        if marker in (0xD9, 0xDA):  # EOI / SOS
            break

        if i + 2 > n:
            break
        seg_len = int.from_bytes(data[i:i+2], "big")
        i += 2
        if seg_len < 2 or i + seg_len - 2 > n:
            break

        payload = data[i:i + seg_len - 2]
        i += seg_len - 2
        segments.append((marker, payload))

    return segments


def has_c2pa_metadata(path: Union[str, Path]) -> Dict[str, Any]:
    """
    Detect C2PA / Content Credentials.
    Returns: { has_c2pa: bool, status: 'yes'|'maybe'|'no', signals: [...] }
    """
    data = Path(path).read_bytes()
    lower = data.lower()
    signals: List[str] = []

    is_jpeg = data[:2] == b"\xFF\xD8"
    is_png = data[:8] == b"\x89PNG\r\n\x1a\n"
    is_webp = data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    is_isobmff = len(data) > 12 and data[4:8] == b"ftyp"

    if is_jpeg:
        signals.append("container:jpeg")
        segments = _parse_jpeg_segments(data)
        app11 = [p for m, p in segments if m == 0xEB]
        if app11:
            signals.append(f"jpeg:app11_count={len(app11)}")
            for p in app11:
                if b"jumb" in p.lower():
                    signals.append("jpeg:jumb_found")
                    return {"has_c2pa": True, "status": "yes", "signals": signals}
            return {"has_c2pa": False, "status": "maybe", "signals": signals}

    if is_isobmff:
        signals.append("container:isobmff")
        if b"jumb" in data:
            signals.append("isobmff:jumb_found")
            return {"has_c2pa": True, "status": "yes", "signals": signals}
        return {"has_c2pa": False, "status": "maybe", "signals": signals}

    if is_png:
        signals.append("container:png")
        if b"xmp" in lower:
            signals.append("png:xmp_present")
        if b"c2pa" in lower or b"urn:c2pa:" in lower:
            signals.append("png:c2pa_string")
            return {"has_c2pa": True, "status": "yes", "signals": signals}
        if "png:xmp_present" in signals:
            return {"has_c2pa": False, "status": "maybe", "signals": signals}

    if is_webp:
        signals.append("container:webp")
        if b"xmp" in lower:
            signals.append("webp:xmp_present")
        if b"c2pa" in lower or b"urn:c2pa:" in lower:
            signals.append("webp:c2pa_string")
            return {"has_c2pa": True, "status": "yes", "signals": signals}
        if "webp:xmp_present" in signals:
            return {"has_c2pa": False, "status": "maybe", "signals": signals}

    if b"urn:c2pa:" in lower or b"contentcredentials" in lower:
        signals.append("generic:c2pa_string")
        return {"has_c2pa": True, "status": "yes", "signals": signals}

    return {"has_c2pa": False, "status": "no", "signals": signals}


# =========================================================
# GUI APPLICATION
# =========================================================

class MetadataRemoverApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Image Metadata Inspector & Cleaner")
        self.root.geometry("900x600")

        self.original_image: Image.Image | None = None
        self.clean_image: Image.Image | None = None
        self.image_path: str | None = None

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

        self.preview = tk.Label(content, text="Upload an image", bg="#ddd")
        self.preview.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=(0, 10))

        meta = tk.Frame(content, width=250, bd=1, relief=tk.SUNKEN)
        meta.pack(side=tk.RIGHT, fill=tk.Y)
        meta.pack_propagate(False)

        tk.Label(meta, text="Metadata detected", font=("Helvetica", 12, "bold")).pack(pady=10)

        self.meta_vars = {
            "EXIF": tk.BooleanVar(),
            "IPTC": tk.BooleanVar(),
            "XMP": tk.BooleanVar(),
            "C2PA": tk.BooleanVar(),
        }

        for k, v in self.meta_vars.items():
            tk.Checkbutton(meta, text=k, variable=v, state=tk.DISABLED).pack(anchor="w", padx=10)

        self.status = tk.Label(main, text="Ready", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

    # -----------------------------------------------------

    def upload_image(self):
        path = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp")]
        )
        if not path:
            return

        try:
            self.image_path = path
            self.original_image = Image.open(path)
            preview = self.original_image.copy()
            preview.thumbnail((550, 550))
            self.tk_img = ImageTk.PhotoImage(preview)
            self.preview.config(image=self.tk_img, text="")
            self.run_btn.config(state=tk.NORMAL)
            self.save_btn.config(state=tk.DISABLED)
            self.clean_image = None
            self.detect_metadata()
            self.status.config(text=f"Loaded: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # -----------------------------------------------------

    def detect_metadata(self):
        for v in self.meta_vars.values():
            v.set(False)

        if not self.original_image or not self.image_path:
            return

        if self.original_image.getexif():
            self.meta_vars["EXIF"].set(True)

        info = self.original_image.info
        if "iptc" in info:
            self.meta_vars["IPTC"].set(True)
        if "xmp" in info or "XML:com.adobe.xmp" in info:
            self.meta_vars["XMP"].set(True)

        c2pa = has_c2pa_metadata(self.image_path)
        if c2pa["status"] in ("yes", "maybe"):
            self.meta_vars["C2PA"].set(True)

        self.status.config(
            text=f"C2PA status: {c2pa['status']} | signals: {', '.join(c2pa['signals'])}"
        )

    # -----------------------------------------------------

    def process_image(self):
        if not self.original_image:
            return
        try:
            self.clean_image = Image.frombytes(
                self.original_image.mode,
                self.original_image.size,
                self.original_image.tobytes(),
            )
            self.save_btn.config(state=tk.NORMAL)
            self.status.config(text="Image processed (pixel-only, metadata removed)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # -----------------------------------------------------

    def download_image(self):
        if not self.clean_image or not self.image_path:
            return

        base, ext = os.path.splitext(os.path.basename(self.image_path))
        out = filedialog.asksaveasfilename(
            initialfile=f"{base}_clean{ext}",
            defaultextension=ext,
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg"), ("All files", "*.*")]
        )
        if not out:
            return

        try:
            self.clean_image.save(out)
            self.status.config(text=f"Saved: {os.path.basename(out)}")
            messagebox.showinfo("Done", "Image saved successfully")
        except Exception as e:
            messagebox.showerror("Error", str(e))


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    root = tk.Tk()
    MetadataRemoverApp(root)
    root.mainloop()
