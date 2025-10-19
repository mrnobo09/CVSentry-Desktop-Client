from fastapi import FastAPI


app = FastAPI(
    title="Face Detection API",
    version="0.1.0",
    description="Basic FastAPI server to accept images for face detection"
)

@app.get("/")
async def root():
    return {"status": "ok", "message": "Face Detection API"}

