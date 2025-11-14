from fastapi import applications
from fastapi.openapi.docs import get_swagger_ui_html


def swagger_local(
    swagger_js_url="./assets/swagger-ui/swagger-ui-bundle.js",
    swagger_css_url="./assets/swagger-ui/swagger-ui.css",
):
    def swagger_ui_source_local(*args, **kwargs):
        return get_swagger_ui_html(
            *args,
            **kwargs,
            swagger_js_url=swagger_js_url,
            swagger_css_url=swagger_css_url,
        )

    applications.get_swagger_ui_html = swagger_ui_source_local