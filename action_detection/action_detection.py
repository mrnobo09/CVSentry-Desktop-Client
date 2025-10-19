from fastapi import FastAPI

app = FastAPI(title="Action Detection Server")


@app.get("/")
async def read_root():
    return {"message": "Action Detection Server"}

