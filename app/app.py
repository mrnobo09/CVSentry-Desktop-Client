from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.camera_routes import router as camera_routes

app = FastAPI()

origins = [
    "http://127.0.0.1:5137",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(camera_routes, prefix="/cameras")


@app.get("/")
async def read_root():
    return {"message": "Main App"}


