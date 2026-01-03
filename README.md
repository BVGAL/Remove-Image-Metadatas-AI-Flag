# AI Image Metadata Inspector & Cleaner

This Python application allows you to **inspect and remove metadata from images while preserving the original resolution**.  
For example, an Instagram post will no longer display the “AI information”.

<p align="center">
  <img src="https://github.com/user-attachments/assets/83440189-2679-44ae-916c-970edb3a21b5" width="700">
</p>

---

## Installation

### Requirements

Python **3.10+** recommended.

Install dependencies:

```bash
pip install -r requirements.txt
```

## How the AI Likelihood Works

The evaluation is based on **metadata coherence**, not visual analysis.

### Signals considered

**C2PA / Content Credentials**
- Strongest indicator when present

**EXIF camera consistency**
- Camera Make + Model + DateTimeOriginal  
- Helps distinguish real camera captures from converted or exported files

**XMP / IPTC metadata**
- Indicates editing or software processing  
- May include AI tools, but not always

### What this tool does *not* do

- ❌ No pixel-level or neural network analysis  
- ❌ No AI image detection via visual patterns  
- ❌ No guarantee of AI / non-AI classification  

This mirrors how many platforms combine metadata with additional internal signals.



