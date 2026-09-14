from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardResultsPagination(PageNumberPagination):
    """
    Standard paginator used across all list endpoints.

    Query Params:
        page        — Page number (1-indexed, default: 1)
        page_size   — Items per page (default: 20, max: 100)

    Response shape is compatible with the DreamscapeJSONRenderer envelope:
        {
            "count": 120,
            "next": "https://.../api/v1/trips/?page=3",
            "previous": "https://.../api/v1/trips/?page=1",
            "results": [ ... ]
        }
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.page.paginator.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "required": ["count", "results"],
            "properties": {
                "count": {
                    "type": "integer",
                    "example": 120,
                },
                "next": {
                    "type": "string",
                    "nullable": True,
                    "format": "uri",
                    "example": "https://api.dreamscapetreks.com/api/v1/trips/?page=3",
                },
                "previous": {
                    "type": "string",
                    "nullable": True,
                    "format": "uri",
                    "example": "https://api.dreamscapetreks.com/api/v1/trips/?page=1",
                },
                "results": schema,
            },
        }
