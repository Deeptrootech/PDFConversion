import io
import os

from PyPDF2 import PdfReader, PdfWriter, PageObject
from reportlab.lib.utils import ImageReader  # ReportLab’s ImageReader can’t open SVG files directly
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4

from ConversionApp.utils import get_file_path, convert_svg_to_png_image


# def create_title_page(text: str = "Page Title") -> io.BytesIO:
#     """
#        Creates a single-page PDF containing centered text, typically used as a section divider
#        (here, used to indicate the start of the original document in a merged PDF).
#
#        Usecase of Canvas:
#        If you're creating PDFs from scratch and not modifying existing files, canvas.Canvas is your best tool.
#     """
#     buffer = io.BytesIO()
#     c = canvas.Canvas(buffer, pagesize=A4)
#     width, height = A4
#
#     # add middle text in bytesIo
#     c.setFont("Helvetica-Bold", 20)
#     c.drawCentredString(width / 2, height / 2, text)  # moddle of page
#
#     c.showPage()
#     c.save()
#     buffer.seek(0)
#     return buffer
#
#
def remove_content_from_left_bottom(rectangle_width=55, rectangle_height=20) -> io.BytesIO:
    """
    here, I have added a rectangle left bottom corner of the PDF.
    To hide its pagination.

    (Note: It's Not necessary that all pdfs hase pagination in left-bottom corner)
    """
    buffer = io.BytesIO()
    width, height = A4
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setFillColorRGB(1, 1, 1)  # White color
    c.rect(width - rectangle_width, 20, rectangle_width, rectangle_height, fill=True, stroke=False)
    c.save()
    buffer.seek(0)
    return buffer


def create_header_page(logo_path="static/images/Logo.svg") -> io.BytesIO:
    """
    Create a PDF page with a header that includes:
    - An optional image/logo at the top-left
    - Text on the top-left and top-right
    - A horizontal line separator under the header
    """
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=A4)
    width, height = A4

    # Font and color
    c.setFont("Helvetica", size=12)
    c.setFillColor(HexColor("#808080"))

    # Draw logo if provided
    logo_temp_path = None
    if logo_path:
        try:
            logo_temp_path = get_file_path(logo_path)
            if logo_path.endswith(".svg"):
                image = convert_svg_to_png_image(logo_temp_path)
            else:
                image = ImageReader(logo_temp_path)
            c.drawImage(image, 30, height - 70, width=100, height=100, preserveAspectRatio=True, mask='auto')
        except Exception as e:
            print(f"Failed to load image: {e}")
        finally:
            # Clean up temp file if created
            if logo_temp_path and os.path.exists(logo_temp_path):
                print(f"Removing temp file: {logo_temp_path}")

    # Draw header text
    c.drawRightString(width - 30, height - 25, "Exfiles AI")

    # Draw separator line
    c.setStrokeColor("#808080")
    c.setLineWidth(0.5)
    c.line(0, height - 35, width, height - 35)

    c.save()
    packet.seek(0)
    return packet


def create_footer_page(all_pages_length: int, current_page: int) -> io.BytesIO:
    """
    Create a PDF page with a footer at the bottom-left.
    """
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=A4)
    width, height = A4

    # Set font and color
    c.setFont("Helvetica", size=9)

    c.setFillColor(HexColor("#808080"))

    # Draw footer at bottom-left
    footer_text = f"Page {current_page} of {all_pages_length}"
    c.drawString(width - 80, 30, footer_text)

    c.save()
    packet.seek(0)
    return packet


def merge_pdfs(pdf_files: list[io.BytesIO]) -> io.BytesIO:
    """
    Merge multiple PDF file-like objects, add footers, and return as a single BytesIO.

    step 1: collect all pages
    step 2: add footers in each page & write into pdf and prepare whole pdf.

    ********** Most IMP For PDF Manipulation: **********
    If you want to modify (add/remove/overlay) content on an existing PDF page, you must:
        - Create a new page (canvas) with the same dimensions.
        - Draw your changes on that canvas (e.g., white block, footer text, watermark, etc.).
        - Merge the canvas with the original page using .merge_page().
    (see below, step 2a, 2b, 2c, 2d)

     Typical Use Cases
        Goal	                                                 Solution
    Add footer/header  (here, 2c)	                Create a canvas with text → merge with page
    Remove content (here, 2b)	                    Overlay a white rectangle → merge
    Add watermark/logo	                            Draw on canvas → merge
    Standardize size/layout (here, 2a)	            Create blank page of fixed size → merge original on top
    """
    writer = PdfWriter()
    all_pages = []
    max_width = 0
    max_height = 0
    # Step 1: Collect all pages and record the maximum page size (width, height)
    for pdf_io in pdf_files:
        reader = PdfReader(pdf_io)
        for page in reader.pages:
            all_pages.append(page)
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)
            max_width = max(max_width, width)
            max_height = max(max_height, height)

    # Step 2: Process each page
    for page_index, page in enumerate(all_pages, start=1):
        # Step 2a: Normalize page size (set size of which page has max page size)
        resized_page = PageObject.create_blank_page(width=max_width, height=max_height)
        resized_page.merge_page(page)

        # Step 2b: Remove old footer (overlay white)
        white_overlay_pdf = PdfReader(remove_content_from_left_bottom())
        resized_page.merge_page(white_overlay_pdf.pages[0])

        # Step 2c: Add new footer (overlay text)
        footer_pdf = PdfReader(create_footer_page(len(all_pages), page_index))
        resized_page.merge_page(footer_pdf.pages[0])

        # Step 2d: Add header (overlay text)
        footer_pdf = PdfReader(create_header_page())
        resized_page.merge_page(footer_pdf.pages[0])

        # Add final page to output
        writer.add_page(resized_page)

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return output
