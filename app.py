import os
from fastapi import FastAPI, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve built frontend static files
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

@app.get("/")
async def root():
    return FileResponse("index.html")

@app.get("/{path:path}")
async def catch_all(path: str):
    if path == "":
        return FileResponse("index.html")
    file_path = os.path.join(os.getcwd(), path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
    return FileResponse("index.html")

# Health check endpoint (matches original backend)
@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
