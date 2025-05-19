import io
import os

import markdown
from django.conf import settings
from django.http import HttpResponse
from rest_framework.response import Response
from weasyprint import HTML
from datetime import datetime
from django.template.loader import render_to_string
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from ConversionApp.pdf_merger import merge_pdfs
from ConversionApp.converters import LocalFileToPdfConverter
from ConversionApp.utils import get_file_path


class ConvertAndMergeView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        stored_pdfs = []
        temp_files_to_delete = []
        # from below file stored in memory or at disc's temp folder based on size
        files = request.FILES.getlist("documents")
        raw_text = request.data.get("text_content", "").strip()
        # ***** Step 1: *****
        # (1st page of final PDF) If provided then This will be the first page of final pdf.
        if raw_text:
            # step (i): Get raw text from request and format same.
            formatted_summary = markdown.markdown(raw_text, extensions=['nl2br'])
            # Step (ii): Render HTML context and Generate HTML string.
            # In case If you want to set specific structure of "raw_text pdf".
            html_string = render_to_string("document_summary_template.html", {
                'document_title': "My Organization Name",
                'summary_generated_date': datetime.now().strftime('%m-%d-%Y'),
                'summary': formatted_summary,
                'static_url_domain': settings.S3_URL if settings.USE_S3 else settings.BACKEND_URL,
            })
            # Step (iii): Create in-memory PDF
            summary_pdf_memory = io.BytesIO()
            HTML(string=html_string).write_pdf(target=summary_pdf_memory, page_size="A4")
            summary_pdf_memory.seek(0)

            # Step (iv): append to list
            stored_pdfs.append(summary_pdf_memory)

        # ***** Step 2: get all uploaded files and append to list. *****
        try:
            # Other Pages of Final PDF:
            for file in files:
                try:
                    # Step (i): Get file from anywhere whether it's stored in Inmemory(RAM), disc(tmp), disc(media) or S3 or In any other storage.
                    # and Store that file to disc's (temp folder) If not stored. then return newly stored path.
                    # here, we know this files are uploaded. so, surely initally it stored in either Imemory or disc(tmp).
                    file_path = get_file_path(file)
                    temp_files_to_delete.append(file_path)  # Track temp file to delete later
                    # Step (ii): Convert file to PDF
                    # we already file stored on disc (from step 1), now it's our local file. so we can use LocalFileToPdfConverter()
                    converter = LocalFileToPdfConverter()
                    doc_pdf_memory = converter.convert(
                        file_path)  # converted to PDF and stored in memory (RAM) as BytesIO (Binarystream).
                except ValueError as e:
                    return Response([str(e)], status=400)
                doc_pdf_memory.seek(0)
                stored_pdfs.append(doc_pdf_memory)  # all PDF file as bytesIo, added in stored_pdfs list.

            # Step 3: Merge all PDFs
            merged_pdf = merge_pdfs(stored_pdfs)  # return as BytesIO of merged PDF.
            response = HttpResponse(merged_pdf, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="merged_output.pdf"'
            return response
        finally:
            # Cleanup temporary files
            for temp_path in temp_files_to_delete:
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except Exception as e:
                    print(f"⚠️ Failed to delete temp file: {temp_path} — {e}")
