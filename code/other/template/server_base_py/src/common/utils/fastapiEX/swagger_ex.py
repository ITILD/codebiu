from fastapi import applications
from fastapi.openapi.docs import get_swagger_ui_html

def swagger_ui_source_local(*args, **kwargs):
    return get_swagger_ui_html(
        *args,
        **kwargs,
        swagger_js_url='https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.29.1/swagger-ui-bundle.min.js',
        swagger_css_url='https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.29.1/swagger-ui.css',
    )

applications.get_swagger_ui_html = swagger_ui_source_local