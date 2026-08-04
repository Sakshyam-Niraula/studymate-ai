from flask import Flask, render_template, request
import ollama
import fitz
import os

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
TEXT_FILE = "study_material.txt"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# =========================
# HOME
# =========================

@app.route("/")
def home():
    return render_template("index.html")


# =========================
# UPLOAD PDF
# =========================

@app.route("/upload", methods=["POST"])
def upload():

    pdf = request.files.get("pdf")

    if pdf is None or pdf.filename == "":
        return render_template(
            "index.html",
            error="Please choose a PDF."
        )

    filepath = os.path.join(
        app.config["UPLOAD_FOLDER"],
        pdf.filename
    )

    pdf.save(filepath)

    try:

        document = fitz.open(filepath)

        text = ""

        for page_number, page in enumerate(document):

            page_text = page.get_text()

            print(
                f"Page {page_number + 1}: "
                f"{len(page_text)} characters"
            )

            text += page_text + "\n"

        document.close()

    except Exception as e:

        return render_template(
            "index.html",
            error=f"Could not read PDF: {e}"
        )

    text = text.strip()

    print("\n==============================")
    print("PDF TEXT EXTRACTION")
    print("==============================")
    print("File:", pdf.filename)
    print("Characters:", len(text))
    print("==============================\n")

    if len(text) == 0:

        return render_template(
            "index.html",
            filename=pdf.filename,
            error=(
                "This PDF contains no selectable text. "
                "OCR is required for this PDF."
            )
        )

    with open(TEXT_FILE, "w", encoding="utf-8") as file:
        file.write(text)

    return render_template(
        "index.html",
        filename=pdf.filename,
        success=f"PDF uploaded! Extracted {len(text)} characters."
    )


# =========================
# ASK QUESTION
# =========================

@app.route("/ask", methods=["POST"])
def ask():

    question = request.form.get("question", "").strip()

    if not question:

        return render_template(
            "index.html",
            error="Please enter a question."
        )

    if not os.path.exists(TEXT_FILE):

        return render_template(
            "index.html",
            error="Please upload a PDF first."
        )

    with open(TEXT_FILE, "r", encoding="utf-8") as file:
        study_material = file.read()

    prompt = f"""
Use the study notes below to answer the question.

NOTES:
{study_material}

QUESTION:
{question}

Answer briefly.
"""

    try:

        response = ollama.chat(
            model="tinyllama",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            options={
                "temperature": 0.1
            }
        )

        answer = response["message"]["content"]

        return render_template(
            "index.html",
            answer=answer
        )

    except Exception as e:

        print("Ollama error:", e)

        return render_template(
            "index.html",
            error=f"AI error: {e}"
        )


# =========================
# GENERATE MCQs
# =========================

@app.route("/quiz", methods=["POST"])
def quiz():

    if not os.path.exists(TEXT_FILE):

        return render_template(
            "index.html",
            error="Please upload a PDF first."
        )

    with open(TEXT_FILE, "r", encoding="utf-8") as file:
        study_material = file.read()

    if not study_material.strip():

        return render_template(
            "index.html",
            error="No study material found."
        )

    print("\n==============================")
    print("GENERATING 5 MCQs")
    print("==============================")
    print("Study material characters:", len(study_material))
    print("==============================\n")

    prompt = f"""
Create 5 MCQs from these study notes.

NOTES:
{study_material}

Each question needs 4 options: A, B, C, D.

Give the correct answer after each question.

Example:

1. What is looping?
A. Option one
B. Option two
C. Option three
D. Option four
Answer: A

Create exactly 5 questions.
"""

    try:

        response = ollama.chat(
            model="tinyllama",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            options={
                "temperature": 0.2
            }
        )

        quiz_questions = response["message"]["content"]

        print("\n==============================")
        print("QUIZ GENERATED")
        print("==============================")
        print(quiz_questions)
        print("==============================\n")

        # Detect if TinyLlama simply repeated the prompt
        if (
            "Create 5 MCQs from these study notes" in quiz_questions
            or "NOTES:" in quiz_questions
        ):

            return render_template(
                "index.html",
                error=(
                    "The AI model did not generate a quiz. "
                    "It repeated the prompt. Try again."
                )
            )

        return render_template(
            "index.html",
            quiz=quiz_questions
        )

    except Exception as e:

        print("Ollama error:", e)

        return render_template(
            "index.html",
            error=f"AI error: {e}"
        )


# =========================
# START SERVER
# =========================

if __name__ == "__main__":

    app.run(debug=True)