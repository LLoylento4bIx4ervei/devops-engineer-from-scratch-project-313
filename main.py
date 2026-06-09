from fastapi import FastAPI

app = FastAPI(title="Ping App")

@app.get("/ping")
def ping():
	return "pong"
