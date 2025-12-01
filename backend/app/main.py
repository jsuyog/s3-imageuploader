from ctypes import sizeof
import os
from fastapi import FastAPI, File, UploadFile, HTTPException
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import List
import shutil
import uuid

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


#location of image storage
IMAGESTORAGELOCATION = Path(__file__).parent.parent.parent / "uploadedfiles"
IMAGESTORAGELOCATION.mkdir(parents=True, exist_ok=True)

app.mount("/uploadedfiles", StaticFiles(directory=IMAGESTORAGELOCATION), name="uploadedfiles")


def filesize(file):
    file.file.seek(0, 2)                 # end
    size_bytes = file.file.tell()        # size
    file.file.seek(0)                     # go back to start

    size_mb = size_bytes / (1024 * 1024)

    return size_mb


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/recent")
def get_recentfiles():
    files: List[dict] = []  

    for entry in IMAGESTORAGELOCATION.iterdir():
        if entry.is_file():
            stat = entry.stat()
            files.append({
                "filename": entry.name,
                "size_bytes": stat.st_size,
                "modified_time": stat.st_mtime,
                "size_mb": stat.st_size / (1024 * 1024),
                "url": f"/uploadedfiles/{entry.name}"
            })
    files.sort(key=lambda x: x["modified_time"], reverse=True)
    recent = files
    return {"images":recent}


@app.post("/uploadfile")
async def upload_file(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        return {"error": "Only image files are allowed."}
    
    if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
        return {"error": "File extension not allowed. Only .png, .jpg, .jpeg, .gif are allowed."}
    
    original_name = file.filename
    ext = Path(original_name).suffix  # e.g. ".jpg"
    unique_name = f"{uuid.uuid4().hex}{ext}"

    fileldata = {
        "original_name": original_name,
        "unique_name": unique_name,
        "content_type": file.content_type,
        "size_bytes": filesize(file)
    }

    file_path = IMAGESTORAGELOCATION / unique_name

    try:
        with file_path.open("wb") as buffer:
            content = await(file.read())
            buffer.write(content)
            
            # shutil.copyfileobj(file.file, buffer)            

    except Exception as e:
        return {"error": f"Failed to save file: {e}"}
    
    finally:
        file.file.close()


    return fileldata