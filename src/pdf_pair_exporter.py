import os
from io import BytesIO
from typing import Optional, Union

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


ImgLike = Union[str, bytes]  # filepath OR raw PNG bytes


class PDFPairExporter:
    """
    Writes a single-page PDF with two charts vertically stacked.
    Top: technical
    Bottom: performance
    """

    def __init__(self, pagesize=landscape(letter), margin_in: float = 0.4, gutter_in: float = 0.25):
        self.pagesize = pagesize
        self.margin_in = margin_in
        self.gutter_in = gutter_in

    def _to_imagereader(self, img: ImgLike) -> ImageReader:
        if isinstance(img, bytes):
            return ImageReader(BytesIO(img))
        return ImageReader(img)

    def export(
        self,
        perf_img: ImgLike,
        tech_img: ImgLike,
        output_pdf_path: str,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        top_label: str = "Technical",
        bottom_label: str = "Performance",
    ) -> str:
        out_dir = os.path.dirname(output_pdf_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        c = canvas.Canvas(output_pdf_path, pagesize=self.pagesize)
        page_w, page_h = self.pagesize

        margin = self.margin_in * inch
        gutter = self.gutter_in * inch

        header_h = 0.6 * inch if (title or subtitle) else 0.0

        usable_w = page_w - 2 * margin
        usable_h = page_h - 2 * margin - header_h - gutter

        cell_h = usable_h / 2
        cell_w = usable_w

        def draw_header():
            y = page_h - margin
            if title:
                c.setFont("Helvetica-Bold", 14)
                c.drawString(margin, y + 0.05 * inch, title)
                y -= 0.3 * inch
            if subtitle:
                c.setFont("Helvetica", 10)
                c.drawString(margin, y - 0.05 * inch, subtitle)

        def draw_image(img_obj: ImgLike, x: float, y: float, w: float, h: float):
            img = self._to_imagereader(img_obj)
            iw, ih = img.getSize()
            scale = min(w / iw, h / ih)
            draw_w = iw * scale
            draw_h = ih * scale
            cx = x + (w - draw_w) / 2
            cy = y + (h - draw_h) / 2
            c.drawImage(img, cx, cy, width=draw_w, height=draw_h, mask="auto")

        draw_header()

        content_top = page_h - margin - header_h

        # --- Top chart (technical) ---
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin, content_top - 14, top_label)

        top_y = content_top - 14 - cell_h
        try:
            draw_image(tech_img, margin, top_y, cell_w, cell_h - 18)
        except Exception:
            c.setFont("Helvetica", 10)
            c.drawString(margin, top_y + cell_h / 2, "Failed to render technical chart")

        # --- Bottom chart (performance) ---
        bottom_label_y = top_y - gutter
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin, bottom_label_y - 14, bottom_label)

        bottom_y = bottom_label_y - 14 - cell_h
        try:
            draw_image(perf_img, margin, bottom_y, cell_w, cell_h - 18)
        except Exception:
            c.setFont("Helvetica", 10)
            c.drawString(margin, bottom_y + cell_h / 2, "Failed to render performance chart")

        c.showPage()
        c.save()
        return output_pdf_path
