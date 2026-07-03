
import os
from pydoc import text
import re
import uuid
import traceback
import fitz

from fastapi import FastAPI, UploadFile, File

import firebase_admin
from firebase_admin import credentials, firestore

print("PROJECT:", os.getenv("FIREBASE_PROJECT_ID"))
print("EMAIL:", os.getenv("FIREBASE_CLIENT_EMAIL"))


# ==========================================
# FASTAPI
# ==========================================

app = FastAPI(
    title="Success Point PDF Ingestion API"
)
@app.get("/")
def home():
    return {
        "status": "running",
        "message": "Success Point Backend Live"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }
    
# ==========================================
# FIREBASE
# ==========================================
private_key = os.getenv("FIREBASE_PRIVATE_KEY")

if not private_key:
    raise ValueError(
        "FIREBASE_PRIVATE_KEY environment variable not set"
    )

firebase_config = {
    "type": "service_account",
    "project_id": os.getenv("FIREBASE_PROJECT_ID"),
    "private_key": os.getenv("FIREBASE_PRIVATE_KEY").replace("\\n", "\n"),
    "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
    "token_uri": "https://oauth2.googleapis.com/token",
}

cred = credentials.Certificate(firebase_config)
firebase_admin.initialize_app(cred)

db = firestore.client()

# ==========================================
# FOLDERS
# ==========================================

UPLOAD_DIR = "uploads"
IMAGE_DIR = "extracted_images"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)

# ==========================================
# CHAPTER DETECTOR
# ==========================================

def detect_chapter(line):

    line = line.strip()

    if len(line) < 3:
        return False

    patterns = [

        # Chapter 1
        r"^Chapter\s+\d+",

        # 1. Sets
        r"^\d+\.\s+[A-Za-z].{2,}$",

        # 1 Sets
        r"^\d+\s+[A-Za-z].{2,}$",

        # 19.2 Aquatic ecosystem
        r"^\d+\.\d+\s+[A-Za-z].{2,}$",

        # 19.2.1 Something
        r"^\d+\.\d+\.\d+\s+[A-Za-z].{2,}$",

        # Exercise 1.1
        r"^Exercise\s+\d+(\.\d+)?",

        # Unit 1
        r"^Unit\s+\d+",

    ]

    for pattern in patterns:
        if re.match(pattern, line, re.IGNORECASE):
            return True

    return False


# ==========================================
# CHUNKER
# ==========================================

def chunk_text(text, chunk_size=500):

    paragraphs = text.split("\n")

    chunks = []

    current = ""

    for para in paragraphs:

        para = para.strip()

        if not para:
            continue

        if len(current) + len(para) < chunk_size:
            current += "\n" + para
        else:
            chunks.append(current.strip())
            current = para

    if current:
        chunks.append(current.strip())

    return chunks


# ==========================================
# IMAGE STORAGE
# ==========================================

def upload_image(local_path, book_id, chapter_id):

    return local_path


print("===================================")
print("SUCCESS POINT PDF INGESTION")
print("===================================")

# ==========================================
# INGEST BOOK
# ==========================================

from fastapi import Form

@app.post("/ingest-book")
async def ingest_book(
    pdf: UploadFile = File(...),
    class_name: str = Form(...),
    subject: str = Form(...),
    board: str = Form(...),
):

    try:

        print("\nINGESTION STARTED")

        book_id = str(uuid.uuid4())

        pdf_path = os.path.join(
            UPLOAD_DIR,
            pdf.filename
        )

        with open(pdf_path, "wb") as f:
            f.write(await pdf.read())

        print(f"PDF SAVED: {pdf_path}")

        doc = fitz.open(pdf_path)

        print(f"PAGES: {len(doc)}")

        # --------------------
        # BOOK
        # --------------------

        db.collection("books").document(
            book_id
        ).set({
            "bookId": book_id,
            "bookName": pdf.filename,
            "class": class_name,
            "subject": subject,
            "board": board,
            "totalPages": len(doc),
            "createdAt":
                firestore.SERVER_TIMESTAMP
        })

        current_chapter = "Introduction"

        chapter_id = str(uuid.uuid4())

        db.collection("chapters").document(
            chapter_id
        ).set({
            "chapterId": chapter_id,
            "bookId": book_id,
            "chapterName": current_chapter,
            "createdAt":
                firestore.SERVER_TIMESTAMP
        })

        # ==================================
        # PAGE LOOP
        # ==================================

        for page_num in range(len(doc)):

            page = doc[page_num]
            text = page.get_text()

        if page_num < 20:

            print("\n====================")
            print(f"PAGE {page_num + 1}")
            print("====================")
            print(text[:1500])
    
            print("\n========== CONTENTS PAGE FOUND ==========\n")

            chapter_pattern = (
                r"(\d+)\.\s+"
                r"(.+?)"
                r"\s+(\d+)\s+to\s+(\d+)"
            )

            matches = re.findall(
                chapter_pattern,
                text
            )

            print("MATCHES FOUND:")

            for match in matches:
                print(match)

            print("\n========================================\n")

            # ------------------------------
            # CHAPTER DETECTION
            # ------------------------------
            for line in text.split("\n"):

                if detect_chapter(line):

                    current_chapter = line.strip()

                    chapter_id = str(uuid.uuid4())

                    db.collection(
                        "chapters"
                    ).document(
                        chapter_id
                    ).set({
                        "chapterId":
                            chapter_id,
                        "bookId":
                            book_id,
                        "chapterName":
                            current_chapter,
                        "createdAt":
                            firestore.SERVER_TIMESTAMP
                    })

                    print(f"LINE: {line}")
                    print(
                        f"NEW CHAPTER: "
                        f"{current_chapter}"
                    )
                    
            # ------------------------------
            # FULL PAGE IMAGE
            # ------------------------------

            page_image_path = os.path.join(
                IMAGE_DIR,
                f"{book_id}_page_{page_num+1}.png"
            )

            pix = page.get_pixmap(
                matrix=fitz.Matrix(2, 2)
            )

            pix.save(page_image_path)

            db.collection("images").add({
                "bookId": book_id,
                "chapterId": chapter_id,
                "pageNumber":
                    page_num + 1,
                "imageUrl":
                    page_image_path,
                "imageType":
                    "full_page"
            })

            # ------------------------------
            # EMBEDDED IMAGES
            # ------------------------------

            page_images = []

            images = page.get_images(
                full=True
            )

            print(
                f"EMBEDDED IMAGES: "
                f"{len(images)}"
            )

            for img_index, img in enumerate(images):

                xref = img[0]

                base_image = doc.extract_image(
                    xref
                )
                width = base_image.get("width", 0)
                height = base_image.get("height", 0)

                image_bytes = base_image["image"]

                if len(image_bytes) < 10000:
                   continue

                ext = (
                    base_image["ext"]
                )

                image_name = (
                    f"{book_id}_"
                    f"{page_num}_"
                    f"{img_index}.{ext}"
                )

                image_path = os.path.join(
                    IMAGE_DIR,
                    image_name
                )

                with open(
                    image_path,
                    "wb"
                ) as image_file:

                    image_file.write(
                        image_bytes
                    )

                page_images.append(
                    image_path
                )

                db.collection(
                    "images"
                ).add({
                    "bookId":
                        book_id,
                    "chapterId":
                        chapter_id,
                    "pageNumber":
                        page_num + 1,
                    "imageUrl":
                        image_path,
                    "imageType":
                        "embedded"
                })

            # ------------------------------
            # CHUNKS
            # ------------------------------

            if text.strip():

                chunks = chunk_text(
                    text
                )

                print(
                    f"CHUNKS: "
                    f"{len(chunks)}"
                )

                for index, chunk in enumerate(
                    chunks
                ):

                    db.collection(
                        "chapter_chunks"
                    ).add({

                        "bookId":
                            book_id,

                        "chapterId":
                            chapter_id,

                        "chapterName":
                            current_chapter,

                        "pageNumber":
                            page_num + 1,

                        "chunkIndex":
                            index,

                        "wordCount": len(chunk.split()),

                        "text":
                            chunk,

                        "imageUrls":
                            page_images,

                        "createdAt":
                            firestore.SERVER_TIMESTAMP
                    })

        print("INGESTION COMPLETE")
        return {
            "status": "success",
            "bookId": book_id,
            "pages": len(doc)
        }

    except Exception as e:
        traceback.print_exc()
        return {
            "status": "error",
            "message": str(e)
        }
                

def get_chapters(book_id):

    docs = (
        db.collection("chapters")
        .where(
            "bookId",
            "==",
            book_id
        )
        .stream()
    )

    result = []

    for doc in docs:
        result.append(
            doc.to_dict()
        )

    return result


# ==========================================
# GET CHAPTER CONTENT
# ==========================================

@app.get(
    "/chapter-content/{chapter_id}"
)
def get_chapter_content(
    chapter_id
):

    docs = (
        db.collection(
            "chapter_chunks"
        )
        .where(
            "chapterId",
            "==",
            chapter_id
        )
        .stream()
    )

    result = []

    for doc in docs:
        result.append(
            doc.to_dict()
        )

    return result


# ==========================================
# GEMINI CONTEXT ENDPOINT
# ==========================================

@app.get(
    "/chapter-context/{chapter_id}"
)
def get_chapter_context(
    chapter_id
):

    chunk_docs = (
        db.collection(
            "chapter_chunks"
        )
        .where(
            "chapterId",
            "==",
            chapter_id
        )
        .stream()
    )

    chunks = []

    for doc in chunk_docs:
        chunks.append(
            doc.to_dict()
        )

    image_docs = (
        db.collection(
            "images"
        )
        .where(
            "chapterId",
            "==",
            chapter_id
        )
        .stream()
    )

    images = []

    for doc in image_docs:
        images.append(
            doc.to_dict()
        )

    return {
        "chapterId":
            chapter_id,
        "chunks":
            chunks,
        "images":
            images
    }

@app.get("/images/{chapter_id}")
def get_images(chapter_id):

    docs = (
        db.collection("images")
        .where("chapterId", "==", chapter_id)
        .stream()
    )

    return [
        doc.to_dict()
        for doc in docs
    ]
from typing import Optional

from fastapi import Query

@app.get("/books")
def get_books(
    class_name: str = Query(None),
    subject: str = Query(None),
):
    print("CLASS:", class_name)
    print("SUBJECT:", subject)

    query = db.collection("books")

    if class_name:
        query = query.where(
            "class",
            "==",
            class_name,
        )

    if subject:
        query = query.where(
            "subject",
            "==",
            subject,
        )

    docs = query.stream()

    result = []

    for doc in docs:
        result.append(doc.to_dict())

    return result

@app.get("/stats")
def stats():

    books = len(list(db.collection("books").stream()))
    chapters = len(list(db.collection("chapters").stream()))
    chunks = len(list(db.collection("chapter_chunks").stream()))
    images = len(list(db.collection("images").stream()))

    return {
        "books": books,
        "chapters": chapters,
        "chunks": chunks,
        "images": images
    }

@app.get("/chapters/{book_id}")
def get_chapters(book_id):

    docs = (
        db.collection("chapters")
        .where("bookId", "==", book_id)
        .stream()
    )

    result = []

    for doc in docs:
        result.append(doc.to_dict())

    return result

@app.get("/chunks/{chapter_id}")
def get_chunks(chapter_id: str):

    chunks = []

    docs = (
        db.collection("chapter_chunks")
        .where("chapterId", "==", chapter_id)
        .stream()
    )

    for doc in docs:
        data = doc.to_dict()

        chunks.append({
            "chunkId": doc.id,
            "chunkIndex": data.get("chunkIndex"),
            "pageNumber": data.get("pageNumber"),
            "text": data.get("text"),
            "imageUrls": data.get("imageUrls", [])
        })

    chunks.sort(
        key=lambda x: x.get("chunkIndex", 0)
    )

    return chunks

