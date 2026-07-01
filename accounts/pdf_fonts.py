import os
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_FONTS_REGISTERED = False


def register_pdf_fonts():
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return

    candidates = [
        (r'C:\Windows\Fonts\arial.ttf', r'C:\Windows\Fonts\arialbd.ttf'),
        (r'C:\Windows\Fonts\calibri.ttf', r'C:\Windows\Fonts\calibrib.ttf'),
        ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
    ]

    for regular, bold in candidates:
        if os.path.exists(regular) and os.path.exists(bold):
            pdfmetrics.registerFont(TTFont('PdfFont', regular))
            pdfmetrics.registerFont(TTFont('PdfFont-Bold', bold))
            _FONTS_REGISTERED = True
            return

    _FONTS_REGISTERED = True
