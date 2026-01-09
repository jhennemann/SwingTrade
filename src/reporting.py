import os
from typing import List, Optional

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


class PDFGalleryExporter:
    """
    Creates a multi-page PDF gallery from a list of image paths.
    Default layout: 2 columns x 2 rows per page (4 charts/page).
    """

    def __init__(self, pagesize=landscape(letter), cols: int = 2, rows: int = 2, margin_in: float = 0.4):
        self.pagesize = pagesize
        self.cols = cols
        self.rows = rows
        self.margin_in = margin_in

    def export(
        self,
        image_paths: List[str],
        output_pdf_path: str,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
    ) -> str:
        if not image_paths:
            raise ValueError("No images provided to export.")

        out_dir = os.path.dirname(output_pdf_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        c = canvas.Canvas(output_pdf_path, pagesize=self.pagesize)
        page_w, page_h = self.pagesize

        margin = self.margin_in * inch
        gutter = 0.25 * inch

        usable_w = page_w - 2 * margin
        usable_h = page_h - 2 * margin

        cell_w = (usable_w - (self.cols - 1) * gutter) / self.cols
        cell_h = (usable_h - (self.rows - 1) * gutter) / self.rows

        imgs_per_page = self.cols * self.rows

        def draw_header():
            if title:
                c.setFont("Helvetica-Bold", 14)
                c.drawString(margin, page_h - margin + 0.05 * inch, title)
            if subtitle:
                c.setFont("Helvetica", 10)
                c.drawString(margin, page_h - margin - 0.20 * inch, subtitle)

        for page_start in range(0, len(image_paths), imgs_per_page):
            draw_header()

            page_imgs = image_paths[page_start: page_start + imgs_per_page]

            for idx, img_path in enumerate(page_imgs):
                col = idx % self.cols
                row = idx // self.cols  # row 0 is top row in our placement

                x0 = margin + col * (cell_w + gutter)
                y_top = page_h - margin - row * (cell_h + gutter)

                filename = os.path.basename(img_path)
                c.setFont("Helvetica", 9)
                c.drawString(x0, y_top - 12, filename)

                # Image box below caption
                img_x = x0
                img_y = y_top - 12 - cell_h + 6
                img_w = cell_w
                img_h = cell_h - 18

                try:
                    img = ImageReader(img_path)
                    iw, ih = img.getSize()

                    scale = min(img_w / iw, img_h / ih)
                    draw_w = iw * scale
                    draw_h = ih * scale

                    cx = img_x + (img_w - draw_w) / 2
                    cy = img_y + (img_h - draw_h) / 2

                    c.drawImage(img, cx, cy, width=draw_w, height=draw_h, mask="auto")
                except Exception:
                    c.setFont("Helvetica", 10)
                    c.drawString(img_x, img_y + img_h / 2, f"Failed to load: {filename}")

            c.showPage()

        c.save()
        return output_pdf_path
