import uvicorn

if __name__ == "__main__":
    uvicorn.run("src.main:app", reload=True)
