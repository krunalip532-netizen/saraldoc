
from flask import Flask, render_template, request
from pypdf import PdfReader
from docx import Document
import requests
import io

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}


def extract_text(file, extension):
    if extension == "pdf":
        pdf = PdfReader(file)
        text = "\n".join(
            page.extract_text() or "" for page in pdf.pages
        )
    elif extension == "docx":
        document = Document(file)
        text = "\n".join(
            paragraph.text for paragraph in document.paragraphs
        )
    else:
        text = file.read().decode("utf-8-sig", errors="replace")

    return text.strip()


def split_text(text, max_length=4000):
    chunks = []

    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break

        split_at = text.rfind(" ", 0, max_length)
        if split_at <= 0:
            split_at = max_length

        chunks.append(text[:split_at])
        text = text[split_at:].strip()

    return chunks


@app.route("/")
def home():
    return render_template(
        "index.html",
        translated_text="",
        error="",
        filename=""
    )


@app.route("/translate", methods=["POST"])
def translate_document():
    uploaded_file = request.files.get("document")
    target_language = request.form.get("language", "hi")

    if not uploaded_file or not uploaded_file.filename:
        return render_template(
            "index.html",
            translated_text="",
            error="Please select a document first.",
            filename=""
        )

    filename = uploaded_file.filename

    if "." not in filename:
        extension = ""
    else:
        extension = filename.rsplit(".", 1)[-1].lower()

    if extension not in ALLOWED_EXTENSIONS:
        return render_template(
            "index.html",
            translated_text="",
            error="Please upload a PDF, DOCX, or TXT file.",
            filename=filename
        )

    try:
        file_data = io.BytesIO(uploaded_file.read())
        original_text = extract_text(file_data, extension)

        if not original_text:
            raise ValueError(
                "No readable text found. Scanned PDFs need OCR."
            )

        translated_chunks = []

        for chunk in split_text(original_text):
            response = requests.post(
                "http://127.0.0.1:5001/translate",
                json={
                    "q": chunk,
                    "source": "auto",
                    "target": target_language,
                    "format": "text"
                },
                timeout=30
            )

            if response.status_code != 200:
                raise ValueError(
                    f"Translation service returned HTTP "
                    f"{response.status_code}: {response.text[:300]}"
                )

            translated_chunks.append(
                response.json()["translatedText"]
            )

        translated_text = "\n\n".join(translated_chunks)

        return render_template(
            "index.html",
            translated_text=translated_text,
            error="",
            filename=filename
        )

    except Exception as e:
        return render_template(
            "index.html",
            translated_text="",
            error=f"Translation failed: {e}",
            filename=filename
        )


@app.errorhandler(413)
def file_too_large(error):
    return "File too large. Please use a file under 10 MB.", 413


if __name__ == "__main__":
    app.run(debug=True)

