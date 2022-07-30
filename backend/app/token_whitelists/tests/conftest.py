from httpx import HTTPStatusError, Request, Response


def raise_http_status_error_404(_):
    raise HTTPStatusError(
        "mocked http status error",
        request=Request("get", "http://"),
        response=Response(404),
    )


def raise_http_status_error_501(_):
    raise HTTPStatusError(
        "mocked http status error",
        request=Request("get", "http://"),
        response=Response(501),
    )
