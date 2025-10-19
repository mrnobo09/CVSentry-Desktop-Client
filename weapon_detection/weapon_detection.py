from fastapi import FastAPI

app = FastAPI(title="Weapon Detection Server")


@app.get("/")
async def read_root():
    return {"message": "Weapon Detection Server"}

