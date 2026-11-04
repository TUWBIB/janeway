"""
Helpers for accepting base64-encoded images (data URIs or bare base64)
on the writable TUW API and storing them into Django ImageFields.
"""

import base64
import binascii
import io
import re

from django.core.files.base import ContentFile
from django.core.validators import get_available_image_extensions

from rest_framework import serializers

DATA_URI_RE = re.compile(r"^data:(?P<mime>[^;,]+)?(;base64)?,(?P<data>.*)$", re.DOTALL)


def parse_base64_image(value):
    """
    Parse a base64 image payload.

    Accepts either a data URI ("data:image/png;base64,<data>") or a plain
    base64 string. Returns a 2-tuple (extension, byte_content) where the
    extension has no leading dot (e.g. "png"). Raises
    ``serializers.ValidationError`` on malformed input.
    """
    if not isinstance(value, str) or not value.strip():
        raise serializers.ValidationError(
            "Expected a base64-encoded image, either as a data URI "
            "(e.g. 'data:image/png;base64,....') or a plain base64 string."
        )

    value = value.strip()
    extension = None
    match = DATA_URI_RE.match(value)
    if match:
        mime = match.group("mime")
        payload = match.group("data")
        if mime and mime.startswith("image/"):
            # e.g. image/png -> png, image/jpeg -> jpeg
            extension = mime.split("/")[-1].split("+")[0].lower() or None
    else:
        payload = value

    try:
        content = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        raise serializers.ValidationError("Invalid base64 data.")

    if not content:
        raise serializers.ValidationError("The image content is empty.")

    return extension, content


def validate_image_content(content, extension):
    """
    Validate that the decoded bytes look like a supported image and the
    extension is allowed (SVG is checked structurally, raster images
    with PIL).
    """
    from PIL import Image  # local import to keep app startup light

    if not extension:
        raise serializers.ValidationError(
            "Could not determine the image file extension. Provide a data "
            "URI with a MIME type (e.g. 'data:image/png;base64,...')."
        )

    allowed_extensions = get_available_image_extensions() + ["svg"]
    if extension not in allowed_extensions:
        raise serializers.ValidationError(
            "Unsupported file extension '{}'.".format(extension)
        )

    if extension == "svg":
        # SVG content cannot be verified with PIL; check it is at least
        # XML-ish so we do not store garbage.
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            raise serializers.ValidationError("The provided SVG data is not valid UTF-8.")
        if "<svg" not in text[:500].lower():
            raise serializers.ValidationError(
                "The provided data is not a valid SVG image."
            )
    else:
        try:
            image = Image.open(io.BytesIO(content))
            image.verify()
        except Exception:
            raise serializers.ValidationError(
                "The provided data is not a valid image."
            )

    return extension


def assign_base64_image(instance, field_name, payload):
    """
    Decode a base64 image payload and store it into
    ``instance.<field_name>`` (an ImageField).

    On update the previously stored file is deleted from storage so the
    old file does not linger on disk. The instance is saved as part of
    ``FieldFile.save()``.
    """
    extension, content = parse_base64_image(payload)
    validate_image_content(content, extension)

    field = instance._meta.get_field(field_name)
    field_file = getattr(instance, field_name)

    if field_file.name:
        field.storage.delete(field_file.name)

    # FieldFile.save() runs the field's upload_to callable (which derives
    # the extension from the filename we pass here) and saves the instance.
    field_file.save(
        "{}.{}".format(field_name, extension), ContentFile(content), save=True
    )
    return field_file.name
