import email
import io
import os
import subprocess
import tempfile
import pytz
from datetime import datetime
from email import policy
import pandas as pd
from PIL import Image
from weasyprint import CSS, HTML

from pillow_heif import register_heif_opener
register_heif_opener()  # Import and register HEIF support before using Image.open()


class LocalFileToPdfConverter:
    """
    Converts a local file(downloaded to disk) into PDF.
    Handles doc/docx, html, csv, images, and already existing PDFs.

    Note:
        Use This class directly to convert specified file extensions into PDF.
        If...
        You already have a local file on disk.
    """

    def convert(self, file_path: str) -> io.BytesIO:
        """
        Converts a local file into PDF.

        The conversion is done based on the file extension:

        - PDF: The file is returned as is.
        - DOC/DOCX/ODT/TXT/RTF: The file is converted to PDF using LibreOffice in headless mode.
        - HTML/HTM: The file is converted to PDF using WeasyPrint.
        - CSV: The file is converted to PDF using pandas and WeasyPrint.
        - EML: The file is converted to PDF using email and WeasyPrint.
        - XLS/XLSX/ODS: The file is converted to PDF using pandas and WeasyPrint.
        - JPG/JPEG/PNG/WEBP/TIF/TIFF/BMP/GIF/HEIC: The file is converted to PDF using Pillow.

        If the file extension is not recognized, a ValueError is raised.

        :param file_path: The absolute path to the local file. (i.e stored In Anywhere on disc)
        :return: The converted PDF file as a BytesIO stream. (Stored In memory (RAM))
        """
        ext = os.path.splitext(file_path)[1].lower()
        match ext:
            case ".pdf":
                return self._as_is(file_path)
            case ".doc" | ".docx" | ".odt" | ".txt" | ".rtf":
                return self._convert_from_docx_to_pdf(file_path)
            case ".html" | ".htm":
                return self._convert_from_html_to_pdf(file_path)
            case ".csv":
                return self._convert_excel_or_csv_to_pdf(file_path, "csv")
            case ".eml":
                return self._convert_eml_to_pdf(file_path)
            case ".xls" | ".xlsx" | ".ods":
                return self._convert_excel_or_csv_to_pdf(file_path, "excel")
            case ".jpg" | ".jpeg" | ".png" | ".webp" | ".tif" | ".tiff" | ".bmp" | ".gif" | ".heic":
                return self._convert_from_image_to_pdf(file_path)
            case _:
                raise ValueError(f"Unsupported file type: {ext}")

    def _as_is(self, file_path: str) -> io.BytesIO:
        """Read the PDF file and return it as a BytesIO stream."""
        with open(file_path, "rb") as f:
            return io.BytesIO(f.read())

    def _convert_from_docx_to_pdf(self, file_path: str) -> io.BytesIO:
        """
        Convert .doc/.docx/.odt to PDF using LibreOffice in headless mode.
        LibreOffice must be installed on our system.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run([
                "libreoffice", "--headless", "--convert-to", "pdf", "--outdir", tmpdir, file_path
            ], check=True)
            out = os.path.join(tmpdir, os.path.splitext(os.path.basename(file_path))[0] + ".pdf")
            with open(out, "rb") as f:
                return io.BytesIO(f.read())

    def _convert_from_html_to_pdf(self, file_path: str) -> io.BytesIO:
        """Read an HTML file and convert it to PDF(by calling '_convert_html_string_to_pdf')."""
        with open(file_path) as f:
            html = f.read()
        return self._convert_html_string_to_pdf(html)

    def _convert_html_string_to_pdf(self, html_string: str) -> io.BytesIO:
        """Convert raw HTML content to PDF using WeasyPrint."""
        pdf_io = io.BytesIO()
        css = CSS(string="""
                @page {
                    size: A4 portrait;
                    margin: 60px 40px;
                }
            """)

        HTML(string=html_string).write_pdf(pdf_io, stylesheets=[css])
        pdf_io.seek(0)
        return pdf_io

    def _convert_excel_or_csv_to_pdf(self, file_path: str, file_type: str) -> io.BytesIO:
        """
        Read a CSV, xls or xlsx file into a DataFrame, convert to HTML table, then to PDF.
        (Not In use For now)
        """
        if file_type == 'excel':
            df = pd.read_excel(file_path, dtype=str, keep_default_na=False, na_filter=False)
        else:
            df = pd.read_csv(file_path, dtype=str, keep_default_na=False, na_filter=False)

        # Remove 'Unnamed' from column names only
        df.columns = df.columns.str.replace('^Unnamed.*', '', regex=True)
        html_table = df.to_html(index=False)
        # Inject CSS to prevent word breaking and handle wide tables
        html = f"""
                <html>
                <head>
                    <style>
                        body {{
                            font-family: Arial, sans-serif;
                            font-size: 12px;
                            margin: 0;
                        }}
                        table {{
                            width: 100%;
                            border-collapse: collapse;
                            table-layout: auto;
                            word-wrap: break-word;
                        }}
                        th, td {{
                            border: 1px solid #ddd;
                            text-align: left;
                            padding: 4px;
                        }}
                    </style>
                </head>
                <body>
                    {html_table}
                </body>
                </html>
                """

        return self._convert_html_string_to_pdf(html)

    def _convert_eml_to_pdf(self, file_path: str) -> io.BytesIO:
        with open(file_path, 'r', encoding='utf-8') as f:
            msg = email.message_from_file(f, policy=policy.default)

        subject = msg['subject']
        from_ = msg['from']
        to = msg['to']

        utc_time = datetime.strptime(msg['date'], '%a, %d %b %Y %H:%M:%S %z')
        parsed_date = utc_time.astimezone(pytz.timezone('Asia/Kolkata'))
        date = parsed_date.strftime('%d/%m/%Y at %I:%M:%S %p')

        body = ""

        # Extract plain text or HTML body
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == 'text/html':
                    body = part.get_content()
                elif content_type == 'text/plain' and not body:
                    body = part.get_content()
        else:
            body = msg.get_content()

        # Build basic HTML
        html_template = f"""
                <html>
                <head>
                    <style>
                        body {{
                            font-family: Open Sans, sans-serif;
                            font-size: 12px;
                            margin: 20px;
                            max-width: 595px;
                        }}
                    </style>
                </head>
                <body>
                    <h2><b>Subject:</b> {subject}</h2>
                    <p><b>From:</b> {from_}</p>
                    <p><b>To:</b> {to}</p>
                    <p><b>Date:</b> {date}</p>
                    <hr>
                    <div style="max-width: 100%; overflow-wrap: break-word;">{body}</div>
                </body>
                </html>
                """
        return self._convert_html_string_to_pdf(html_template)

    def _convert_from_image_to_pdf(self, file_path: str) -> io.BytesIO:
        """
        Convert an image to a single-page PDF.
        """
        # A4 size in pixels at 72 DPI
        A4_WIDTH, A4_HEIGHT = 595, 842

        img = Image.open(file_path).convert("RGB")

        # Resize image while keeping aspect ratio
        img.thumbnail((A4_WIDTH, A4_HEIGHT), Image.Resampling.LANCZOS)

        # Create a white A4 canvas
        canvas = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), "white")

        # Center the image on the canvas
        x = (A4_WIDTH - img.width) // 2
        y = (A4_HEIGHT - img.height) // 2
        canvas.paste(img, (x, y))

        # Save canvas as PDF
        pdf_io = io.BytesIO()
        canvas.save(pdf_io, format='PDF')
        pdf_io.seek(0)
        return pdf_io

