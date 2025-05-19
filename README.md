# Django File Upload & Storage: Complete Guide

---

## 1. Overview

This document explains **how Django handles file uploads**, where uploaded files are stored temporarily and permanently, and how to work with them across different environments (local disk, cloud storage).

---

## 2. Upload Reception (STEP 1)

When a file is uploaded via an HTML form or API endpoint, Django receives it in two ways depending on the size:

### Based on Size, Django uses:

| File Type                | Storage Location         | Condition                                       |
|--------------------------|--------------------------|-------------------------------------------------|
| `InMemoryUploadedFile`   | RAM (memory)             | File size < `FILE_UPLOAD_MAX_MEMORY_SIZE`      |
| `TemporaryUploadedFile`  | Temp folder on Disk      | File size > `FILE_UPLOAD_MAX_MEMORY_SIZE`      |

### Default Threshold Controlled by:
```python
FILE_UPLOAD_MAX_MEMORY_SIZE = 2.5 * 1024 * 1024  # 2.5MB (default)
```

### Using Files Directly without Permanent Storage:
- If you **just want to use the file temporarily** and not store it permanently (e.g., Just for preview, conversion, or scanning):
  
- Then, No need to worry about where file should be stored (In local (i.e at disc's media_root) or In s3). **We've Just received file here... PERIOD**
  
- No need to go to step 2. Just Use file stored from any below way. As per above defined condition & Cleanup file after use.

  - **2.1)** Memory files (**RAM**): No cleanup needed.
  - **2.2)** Temp files (**At Disc**): Manually delete after use using `os.remove(file.temporary_file_path())`.

 **Remember**:
- **Any uploaded file will always store initially either of above place. Because This is the initial steps to receive File.**
---

## 3. Storing Files Permanently (STEP 2)

In above Step, we have received file & stored at **InMemory** or at TempStorage (i.e **disc's temp folder**).

Now We want to store It permanently, for future use.

So, here comes another Two ways to store File. (Now, Thsese 2 ways will store file permanently.)

Called... Django’s storage system.

### FILE STORAGE Controlled by:
```python
DEFAULT_FILE_STORAGE = '<backend_path>'
```

### 3.1 Local Disk Storage (Default)
```python
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
MEDIA_ROOT = '/app/media/'
```
- Files saved under `MEDIA_ROOT`
- URLs accessed via `MEDIA_URL`

### 3.2 S3 or Cloud Storage
```python
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
```
- Files saved on AWS S3 bucket
- URL example: `https://yourbucket.s3.amazonaws.com/myfile.pdf`

> Uses `django-storages` and environment config like `AWS_ACCESS_KEY_ID`, etc.

---

## 4. FileField / ImageField (Model Save)

```python
class Document(models.Model):
    file = models.FileField(upload_to='documents/')
```

When `instance.file.save(...)` is called:
- File content is saved in storage backend (local/S3... i.e as per specified place In **DEFAULT_FILE_STORAGE**)
- DB only stores **file path or URL**, not content

---

## 5. Accessing File:  (STEP 3)
(1) Directly access like below **How to Access** from its path. (whether file is at memory (RAM), local(temp/), local(media/), s3, etc... )

| File Object Type          | How to Access                                  |
|---------------------------|-------------------------------------------------|
| `InMemoryUploadedFile` #  Above STEP-1: File not saved yet. (Just received)    | `.read()`, `.chunks()`                          |
| `TemporaryUploadedFile` # Above STEP-1: File not saved yet. (Just received)  | `.temporary_file_path()` gives disk path       |
| Storage Path string(i.e MEDIA_ROOT Disk or S3) Above STEP-2: i.e File saved     | Use `default_storage.open(path)` gives gets file-like object from S3 or disk. (i.e just loaded file from s3 or disk to In memory (i.e RAM))             |
| `FieldFile` (from model)  | `.path` (local only), `.url` (works everywhere) |

---
(2) access file based on file object type, Store file into Temporarily on disk and then use that absolute path.
**(See, below Function)**
#### Universal Helper to Get File Path

```python
from django.core.files.storage import default_storage
import tempfile, os

def get_file_path(file_or_path) -> str:
    """
    Temporarily Stores the file on disk and returns its absolute path.

    Accepts:
    - UploadedFile (InMemory/Temporary)
    - File path from DB (saved in..local/S3)
    - File-like objects (also called file loaded in memory (RAM))

    Returns:
    - Temporary file path on disk
    """
    if hasattr(file_or_path, 'temporary_file_path'): #  Above STEP-1: File not saved yet. (Just received)
        # Already stored on disk (TemporaryUploadedFile)
        # Then return it's path directly.
        return file_or_path.temporary_file_path()

    elif hasattr(file_or_path, 'read'): #  Above STEP-1: file not saved yet (Just received)
        # InMemoryUploadedFile or file-like
        # Then store it's copy to disc's as temp file & return it's path.
        suffix = os.path.splitext(file_or_path.name)[1] or ".tmp"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            for chunk in file_or_path.chunks():
                tmp.write(chunk)
            return tmp.name

    elif isinstance(file_or_path, str): #  Above STEP-2 - i.e File saved
        # It's a path from Django storage system (S3/local/etc)
        # Then store it's copy to disc's as temp file & return it's path.
        if not default_storage.exists(file_or_path):
            raise FileNotFoundError(f"{file_or_path} not found in storage")
        suffix = os.path.splitext(file_or_path)[1] or ".tmp"
        with default_storage.open(file_or_path, 'rb') as storage_file:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(storage_file.read())
                return tmp.name

    else:
        raise ValueError("Unsupported input type for file_or_path")
```

- **Use Approach 1:**
  - If you want Just file's stream no need to use it's path.
  - You might just want some its content to use, not whole file to use anywhere(like Image Processing, PDF Merging).
  - For lightweight, stream-based processing.
- **Use Approach 2:**
  - If you want file's path Without thinking about Where File saved.
  - For file-path-dependent tools.

  - If you are PDF Merging, Image Processing (e.g. PIL, PyMuPDF, OpenCV)

#### So, In general, 
- Use Approach-2 for safty, You will always get file path. which is requred for majority work. (see below Best Practices)
---

## 6. File Upload Flow Summary

| Phase             | Action                                                 |
|------------------|--------------------------------------------------------|
| Upload Received  | Stored in memory or temp folder                        |
| Temporary Usage  | Read/process and discard                               |
| Save to Model    | Stored via `DEFAULT_FILE_STORAGE` (disk/S3/etc.)       |
| DB Entry         | Only file path or URL saved                            |
| Retrieval        | Use `default_storage`, `.url`, or `.open()`            |

---

## 7. Best Practices

- ✅ Use `default_storage` for abstraction
- ❌ Don’t depend on `.path` for S3 files (won’t exist)
- ✅ Use helper like `get_file_path()` if local path is required
- 🧹 Clean up temp files manually if created with `delete=False`
- ✅ Check `file.size` to guard large uploads

---

## 8. Example: Process Upload in View

```python
def process_uploaded_file(file):
    local_path = get_file_path(file)
    with open(local_path, 'rb') as f:
        content = f.read()
    os.remove(local_path)  # Cleanup if temp
```

---

## 9. Conclusion

Understanding Django’s upload and storage system helps you:
- Handle memory vs disk behavior correctly
- Choose the right storage backend
- Use files flexibly (disk/S3/streams)
- Clean up when necessary

---
**End of Guide**
