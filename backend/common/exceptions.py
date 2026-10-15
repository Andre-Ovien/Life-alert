from django.core.exceptions import ObjectDoesNotExist, ValidationError as ModelValidationError
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.views import exception_handler

def api_exception_handler(exc, context):
    if isinstance(exc, ObjectDoesNotExist):
        exc = NotFound()
    elif isinstance(exc, ModelValidationError):
        exc = ValidationError('Invalid request identifier or value.')
    return exception_handler(exc, context)
