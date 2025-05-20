import io
import os

from PyPDF2 import PdfReader, PdfWriter, PageObject
from django.shortcuts import get_object_or_404
from reportlab.lib.utils import ImageReader  # ReportLab’s ImageReader can’t open SVG files directly
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4

from ConversionApp.models import WhiteLabelConfig
from ConversionApp.utils import get_file_path, convert_svg_to_png_image


class PDFMerger:
    def __init__(self, client_company_name: str):
        """
        Initialize PDF generator with dynamic data from the database
        """
        # Fetch white-label configuration dynamically
        config = get_object_or_404(WhiteLabelConfig, client_company_name=client_company_name)

        self.company_name = config.client_company_name
        self.logo_path = config.logo.path if config.logo else 'static/images/Logo.svg'
        self.current_document_name = "Default Document Name"  # TODO: need to add current document name iterated through every page
        self.white_rectangle_width = 55
        self.white_rectangle_height = 20

    def create_header_page(self, width, height) -> io.BytesIO:
        """
        Create a PDF page with a header that includes:
        - An optional image/logo at the top-left
        - Text on the top-left and top-right
        - A horizontal line separator under the header
        """
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=A4)

        # Font and color
        c.setFont("Helvetica", size=10)
        c.setFillColor(HexColor("#808080"))

        # Draw logo if provided
        logo_temp_path = None
        if self.logo_path:
            try:
                logo_temp_path = get_file_path(self.logo_path)
                if self.logo_path.endswith(".svg"):
                    image = convert_svg_to_png_image(logo_temp_path)
                else:
                    image = ImageReader(logo_temp_path)
                c.drawImage(image, 20, height - 35, width=80, height=35, preserveAspectRatio=True, mask='auto')
            except Exception as e:
                print(f"Failed to load image: {e}")
            finally:
                # Clean up temp file if created
                if logo_temp_path and os.path.exists(logo_temp_path):
                    print(f"Removing temp file: {logo_temp_path}")

        # Draw header text
        text_width = c.stringWidth(self.current_document_name)
        c.drawString(width - text_width - 30, height - 20, self.current_document_name)

        # Draw separator line
        c.setStrokeColor("#808080")
        c.setLineWidth(0.5)
        c.line(0, height - 35, width, height - 35)

        c.save()
        packet.seek(0)
        return packet

    def create_footer_page(self, all_pages_length: int, current_page: int) -> io.BytesIO:
        """
        Create a PDF page with a footer that includes page numbering at the bottom-left
        and company name at the bottom-right.
        """
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=A4)
        width, height = A4

        # Set font and color
        c.setFont("Helvetica", size=9)
        c.setFillColor(HexColor("#808080"))

        # Draw footer: Company name at bottom-right
        c.drawString(20, 20, self.company_name)

        # Draw footer: Page numbering at bottom-left
        c.drawString(width - 70, 20, f"Page {current_page} of {all_pages_length}")

        c.save()
        packet.seek(0)
        return packet

    def merge_pdfs(self, pdf_files: list[io.BytesIO]) -> io.BytesIO:
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
            white_overlay_pdf = PdfReader(self.remove_content_from_left_bottom())
            resized_page.merge_page(white_overlay_pdf.pages[0])

            # Step 2c: Add new footer (overlay text)
            footer_pdf = PdfReader(self.create_footer_page(len(all_pages), page_index))
            resized_page.merge_page(footer_pdf.pages[0])

            # Step 2d: Add header (overlay text)
            if page_index > 1:
                footer_pdf = PdfReader(
                    self.create_header_page(width=max_width, height=max_height))
                resized_page.merge_page(footer_pdf.pages[0])

            # Add final page to output
            writer.add_page(resized_page)

        output = io.BytesIO()
        writer.write(output)
        output.seek(0)
        return output

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
    def remove_content_from_left_bottom(self) -> io.BytesIO:
        """
        here, I have added a rectangle left bottom corner of the PDF.
        To hide its pagination.

        (Note: It's Not necessary that all pdfs hase pagination in left-bottom corner)
        """
        buffer = io.BytesIO()
        width, height = A4
        c = canvas.Canvas(buffer, pagesize=A4)
        c.setFillColorRGB(1, 1, 1)  # White color
        c.rect(width - self.white_rectangle_width, 20, self.white_rectangle_width, self.white_rectangle_height,
               fill=True, stroke=False)
        c.save()
        buffer.seek(0)
        return buffer
