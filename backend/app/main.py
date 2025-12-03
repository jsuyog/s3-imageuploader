from ctypes import sizeof
import os
from fastapi import FastAPI, File, UploadFile, HTTPException
from dotenv import load_dotenv
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import List
import shutil
import uuid
import boto3
from botocore.exceptions import ClientError

load_dotenv()  # reads .env file and loads into environment variables
app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")

if not AWS_S3_BUCKET:
    raise RuntimeError("AWS_S3_BUCKET environment variable is not set.")


s3_client = boto3.client("s3", region_name=AWS_REGION)

def filesize(file):
    file.file.seek(0, 2)                 # end
    size_bytes = file.file.tell()        # size
    file.file.seek(0)                     # go back to start

    size_mb = size_bytes / (1024 * 1024)

    return size_mb


@app.get("/health")
def health_check():
    return {"status": "ok"}


def generate_presigned_url(bucket, key, expires=3600):
    filee = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires,
    )
    
    return filee


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
    s3_key = f"uploads/{unique_name}"

    fileldata = {
        "original_name": original_name,
        "unique_name": unique_name,
        "content_type": file.content_type,
        "size_bytes": filesize(file)
    }

    try:

        file.file.seek(0)

        s3_client.upload_fileobj(
            file.file,
            AWS_S3_BUCKET,
            s3_key,
            ExtraArgs = {
                "ContentType": file.content_type,
                # "ACL": "public-read"
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file to S3: {str(e)}")
    finally:
        file.file.close()


    file_url = f"https://{AWS_S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"

    url = generate_presigned_url(AWS_S3_BUCKET, s3_key)

    return {
        "file_url": file_url,
        "file_data": fileldata,
        "presigned_url": url
    }