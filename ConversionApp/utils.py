import io
import tempfile
import os
import cairosvg
from django.core.files.storage import default_storage
from reportlab.lib.utils import ImageReader


def convert_svg_to_png_image(svg_path):
    png_bytes = cairosvg.svg2png(url=svg_path)
    return ImageReader(io.BytesIO(png_bytes))


def get_file_path(file_or_path) -> str:
    """
    Temporarily Stores the file on disk if not stored and returns its absolute path.
    # works for any source (Memory, disc(tmp/), disc(media/), S3)

    Accepts:
    - UploadedFile (InMemory/Temporary)
    - File path from DB (saved in...local/S3)
    - File-like objects (also called file loaded in memory (RAM))

    Returns:
    - Temporary file absolute path (full path) on disk
    """
    if hasattr(file_or_path, 'temporary_file_path'):  # For file from Disc's Temp storage
        # Already stored on disk: Return it's path
        return file_or_path.temporary_file_path()

    elif hasattr(file_or_path, 'read'):  # For file from Inmemory storage
        # InMemoryUploadedFile or file-like: write to temp and return path
        suffix = os.path.splitext(file_or_path.name)[1] or ".tmp"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            for chunk in file_or_path.chunks():  # safe for all uploads
                tmp.write(chunk)
            return tmp.name

    elif isinstance(file_or_path, str):  # For file from Disc's Media_root or S3.
        # It's a path from Django storage system (S3/local/etc)
        if not default_storage.exists(file_or_path):
            raise FileNotFoundError(f"{file_or_path} does not exist in storage")

        suffix = os.path.splitext(file_or_path)[1] or ".tmp"
        with default_storage.open(file_or_path, 'rb') as storage_file:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(storage_file.read())
                return tmp.name

    else:
        raise ValueError("Unsupported input type")
