from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_extract_document_endpoint_returns_text_and_metadata():
    response = client.post(
        "/api/v1/documents/extract",
        files={"file": ("lesson.md", b"# Lesson\r\n\r\nContent.  ", "text/markdown")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "text": "# Lesson\n\nContent.",
        "metadata": {
            "filename": "lesson.md",
            "format": "md",
            "character_count": len("# Lesson\n\nContent."),
            "page_count": None,
        },
    }


def test_extract_document_endpoint_returns_readable_error_for_unsupported_format():
    response = client.post(
        "/api/v1/documents/extract",
        files={"file": ("lesson.docx", b"unsupported", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert "Formatos permitidos" in response.json()["detail"]