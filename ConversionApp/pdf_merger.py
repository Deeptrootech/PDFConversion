import io
import os
from typing import List, Tuple
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

        Note: Mapping of page height and width starts from bottom-left corner of the page.
              All size are in pt (points)
        """
        # Fetch white-label configuration dynamically
        config = get_object_or_404(WhiteLabelConfig, client_company_name=client_company_name)

        self.company_name = config.client_company_name
        self.logo_path = config.logo.path if config.logo else 'static/images/Logo.svg'

        # Dynamic page width set using setter method
        # Good Use of setter here...: (Debug why used setter method instead of directly assigning)
        self._page_width, self.page_height = A4
        self.footer_width = self._page_width
        self.footer_white_rectangle_width = self.footer_width
        self.header_width = self._page_width
        self.header_white_rectangle_width = self.header_width

        # Dynamic footer and header height and width
        self.footer_height = config.page_footer_height  # Default 20
        self.footer_white_rectangle_height = self.footer_height
        self.header_height = config.page_header_height  # Default 35
        self.header_white_rectangle_height = self.header_height

        self.page_header_footer_left_width_margin = config.header_footer_left_width_margin  # Default 20
        self.page_header_footer_right_width_margin = config.header_footer_right_width_margin  # Default 20
        # Dynamic Logo height and width
        self.logo_height = self.header_height
        self.logo_width = 80

    @property
    def page_width(self):
        return self._page_width

    @page_width.setter
    def page_width(self, value):
        self._page_width = value
        self.footer_width = self._page_width
        self.footer_white_rectangle_width = self.footer_width
        self.header_width = self._page_width
        self.header_white_rectangle_width = self.header_width

    def create_header_page(self, source) -> io.BytesIO:
        """
        Create a PDF page with a header that includes:
        - An optional image/logo at the top-left
        - Text on the top-left and top-right
        - A horizontal line separator under the header
        """
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=(self.page_width, self.page_height))

        # Font and color
        c.setFont("Helvetica", size=10)
        c.setFillColor(HexColor("#808080"))

        # Draw logo if provided (Left header)
        logo_temp_path = None
        if self.logo_path:
            try:
                logo_temp_path = get_file_path(self.logo_path)
                if self.logo_path.endswith(".svg"):
                    image = convert_svg_to_png_image(logo_temp_path)
                else:
                    image = ImageReader(logo_temp_path)
                c.drawImage(image, self.page_header_footer_left_width_margin, self.page_height - self.logo_height,
                            width=self.logo_width, height=self.logo_height, preserveAspectRatio=True, mask='auto')
            except Exception as e:
                print(f"Failed to load image: {e}")
            finally:
                # Clean up temp file if created
                if logo_temp_path and os.path.exists(logo_temp_path):
                    print(f"Removing temp file: {logo_temp_path}")

        # Draw header text (Right header)
        text_width = c.stringWidth(source)
        c.drawString(self.header_width - text_width - self.page_header_footer_right_width_margin, self.page_height - 20,
                     source)

        # Draw separator line
        c.setStrokeColor("#808080")
        c.setLineWidth(0.5)
        c.line(0, self.page_height - self.header_height, self.header_width, self.page_height - self.header_height)

        c.save()
        packet.seek(0)
        return packet

    def create_footer_page(self, all_pages_length: int, current_page: int) -> io.BytesIO:
        """
        Create a PDF page with a footer that includes page numbering at the bottom-left
        and company name at the bottom-right.
        """
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=(self.page_width, self.page_height))

        # Set font and color
        c.setFont("Helvetica", size=9)
        c.setFillColor(HexColor("#808080"))

        # Draw footer: Company name at bottom-left
        c.drawString(self.page_header_footer_left_width_margin, self.footer_height - 20, self.company_name)

        # Draw footer: Page numbering at bottom-left
        pagination_text = f"Page {current_page} of {all_pages_length}"
        text_width = c.stringWidth(pagination_text)
        c.drawString(self.footer_width - text_width - self.page_header_footer_right_width_margin,
                     self.footer_height - 20,
                     pagination_text)

        c.save()
        packet.seek(0)
        return packet

    # def create_title_page(text: str = "Page Title") -> io.BytesIO:
    #     """
    #        Creates a single-page PDF containing centered text, typically used as a section divider
    #        (here, used to indicate the start of the original document in a merged PDF).
    #
    #        Usecase of Canvas:
    #        If you're creating PDFs from scratch and not modifying existing files, canvas.Canvas is your best tool.
    #     """
    #     buffer = io.BytesIO()
    #     c = canvas.Canvas(buffer, pagesize=(self.page_width, self.page_height))
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
    def remove_existing_content_from_header_footer(self) -> io.BytesIO:
        """
        here, I have added a rectangle at top & bottom of the PDF.
        To hide its Exsting data inplace of header and footer.

        (Note: It's Not necessary that all pdfs has pagination in right-bottom corner)
        """
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=(self.page_width, self.page_height))
        c.setFillColorRGB(1, 1, 1)  # White color
        c.rect(0, 0, self.footer_white_rectangle_width,
               self.footer_white_rectangle_height,
               fill=True, stroke=False)
        c.rect(0, self.page_height - self.header_height, self.header_white_rectangle_width,
               self.header_white_rectangle_height,
               fill=True, stroke=False)
        c.save()
        buffer.seek(0)
        return buffer

    def merge_pdfs(self, pdf_files: List) -> io.BytesIO:
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
        each_page_source_document = []
        max_width = 0
        max_height = 0
        # Step 1: Collect all pages and record the maximum page size (width, height)
        for filename, each_pdf_io in pdf_files:
            reader = PdfReader(each_pdf_io)
            for page in reader.pages:
                all_pages.append(page)
                each_page_source_document.append(filename)
                width = float(page.mediabox.width)
                height = float(page.mediabox.height)
                max_width = max(max_width, width)
                max_height = max(max_height, height)
        self.page_width, self.page_height = max_width, max_height

        # Step 2: Process each page
        for page_index, (page, source) in enumerate(zip(all_pages, each_page_source_document), start=1):
            # Step 2a: Normalize page size (set size of which page has max page size)
            resized_page = PageObject.create_blank_page(width=self.page_width, height=self.page_height)
            resized_page.merge_page(page)

            # Step 2b: Remove old footer (overlay white)
            white_overlay_pdf = PdfReader(self.remove_existing_content_from_header_footer())
            resized_page.merge_page(white_overlay_pdf.pages[0])

            # Step 2c: Add new footer (overlay text)
            footer_pdf = PdfReader(self.create_footer_page(len(all_pages), page_index))
            resized_page.merge_page(footer_pdf.pages[0])

            # Step 2d: Add header (overlay text)
            if page_index > 1:
                footer_pdf = PdfReader(
                    self.create_header_page(source=source))
                resized_page.merge_page(footer_pdf.pages[0])

            # Add final page to output
            writer.add_page(resized_page)

        output = io.BytesIO()
        writer.write(output)
        output.seek(0)
        return output
