from PIL import Image, ImageTk
import tkinter as tk
from tkinter import filedialog, messagebox
import os

class MetadataRemoverApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Metadata Remover")
        self.root.geometry("600x600")

        self.original_image = None
        self.clean_image = None
        self.image_path = None

        # Create a main frame
        main_frame = tk.Frame(root, padx=10, pady=10)
        main_frame.pack(expand=True, fill=tk.BOTH)

        # --- Top frame for buttons ---
        top_frame = tk.Frame(main_frame)
        top_frame.pack(fill=tk.X, pady=5)

        self.upload_button = tk.Button(top_frame, text="Upload Image", command=self.upload_image)
        self.upload_button.pack(side=tk.LEFT)

        self.run_button = tk.Button(top_frame, text="Run", state=tk.DISABLED, command=self.process_image)
        self.run_button.pack(side=tk.LEFT, padx=5)

        self.download_button = tk.Button(top_frame, text="Download", state=tk.DISABLED, command=self.download_image)
        self.download_button.pack(side=tk.LEFT)

        # --- Image preview ---
        self.image_preview = tk.Label(main_frame, text="Upload an image to see a preview", bg="lightgrey")
        self.image_preview.pack(expand=True, fill=tk.BOTH, pady=5)

        # --- Status bar ---
        self.status_label = tk.Label(main_frame, text="Welcome!", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

    def upload_image(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp *.gif")]
        )
        if not file_path:
            return

        try:
            self.image_path = file_path
            self.original_image = Image.open(file_path)
            
            # Create a thumbnail for preview
            preview_image = self.original_image.copy()
            preview_image.thumbnail((550, 550))
            
            self.photo_image = ImageTk.PhotoImage(preview_image)
            self.image_preview.config(image=self.photo_image, text="")
            
            self.status_label.config(text=f"Loaded: {os.path.basename(file_path)}")
            self.run_button.config(state=tk.NORMAL)
            self.download_button.config(state=tk.DISABLED)
            self.clean_image = None

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open image: {e}")
            self.status_label.config(text="Error loading image.")

    def process_image(self):
        if not self.original_image:
            messagebox.showwarning("Warning", "No image loaded.")
            return
        
        try:
            # The core logic to remove metadata
            self.clean_image = Image.frombytes(
                self.original_image.mode, self.original_image.size, self.original_image.tobytes()
            )
            self.status_label.config(text="Image processed. Ready for download.")
            self.download_button.config(state=tk.NORMAL)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to process image: {e}")
            self.status_label.config(text="Error processing image.")

    def download_image(self):
        if not self.clean_image:
            messagebox.showwarning("Warning", "No processed image to save.")
            return

        # Suggest a filename
        original_name, original_ext = os.path.splitext(os.path.basename(self.image_path))
        suggested_filename = f"{original_name}_clean{original_ext}"

        save_path = filedialog.asksaveasfilename(
            initialfile=suggested_filename,
            defaultextension=original_ext,
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg"), ("All Files", "*.*")]
        )
        
        if not save_path:
            return
            
        try:
            self.clean_image.save(save_path)
            self.status_label.config(text=f"Image saved to {os.path.basename(save_path)}")
            messagebox.showinfo("Success", "The clean image has been saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save image: {e}")
            self.status_label.config(text="Error saving image.")

if __name__ == "__main__":
    root = tk.Tk()
    app = MetadataRemoverApp(root)
    root.mainloop()
