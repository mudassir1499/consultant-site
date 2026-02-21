"""
Shared file upload validation utilities.
"""

from django.core.exceptions import ValidationError

# 5 MB max file size
MAX_UPLOAD_SIZE = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png']


def validate_uploaded_file(file, max_size=MAX_UPLOAD_SIZE, allowed_extensions=None):
    """
    Validate an uploaded file's size and extension.
    
    Returns:
        (bool, str) — (is_valid, error_message)
    """
    if allowed_extensions is None:
        allowed_extensions = ALLOWED_EXTENSIONS

    if file.size > max_size:
        size_mb = max_size / (1024 * 1024)
        return False, f'File "{file.name}" exceeds the maximum size of {size_mb:.0f}MB.'

    ext = file.name.rsplit('.', 1)[-1].lower() if '.' in file.name else ''
    if ext not in allowed_extensions:
        return False, f'File "{file.name}" has an invalid type. Allowed: {", ".join(allowed_extensions)}.'

    return True, ''


def validate_multiple_files(files_dict, max_size=MAX_UPLOAD_SIZE, allowed_extensions=None):
    """
    Validate multiple uploaded files from request.FILES.
    
    Args:
        files_dict: dict of {field_name: UploadedFile}
    
    Returns:
        (bool, list[str]) — (all_valid, list_of_errors)
    """
    errors = []
    for field_name, file in files_dict.items():
        if file:
            is_valid, error = validate_uploaded_file(file, max_size, allowed_extensions)
            if not is_valid:
                errors.append(error)
    return len(errors) == 0, errors
