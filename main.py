import os
import re
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from sqlalchemy import func
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import Link

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

engine = create_engine(DATABASE_URL, echo=True)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan)


def parse_range(range_str: Optional[str]) -> tuple[int, int]:
    
    if not range_str:
        return 0, 9
    match = re.match(r"^\s*\[\s*(\d+)\s*,\s*(\d+)\s*\]\s*$", range_str)
    if not match:
        return 0, 9
    return int(match.group(1)), int(match.group(2))


@app.get("/ping", response_class=PlainTextResponse)
async def ping():
    return "pong"

def get_session():
    with Session(engine) as session:
        yield session

@app.get("/api/links")
def get_all_links(
    range: Optional[str] = Query(None, alias="range"),
    session: Session = Depends(get_session)
):
    start, end = parse_range(range)
    total = session.exec(select(func.count()).select_from(Link)).one()
    limit = end - start + 1
    links = session.exec(select(Link).offset(start).limit(limit)).all()
    last = min(end, total - 1) if total > 0 else 0
    content_range = f"links {start}-{last}/{total}"
    return JSONResponse(
        content=[link.dict() for link in links],
        headers={"Content-Range": content_range}
    )

@app.post("/api/links", status_code=201)
def create_link(link_data: dict, session: Session = Depends(get_session)):
    original_url = link_data.get("original_url")
    short_name = link_data.get("short_name")
    if not original_url or not short_name:
        raise HTTPException(status_code=400, detail="original_url and short_name are required")

    existing = session.exec(select(Link).where(Link.short_name == short_name)).first()
    if existing:
        raise HTTPException(status_code=409, detail="short_name already exists")

    short_url = f"{BASE_URL}/r/{short_name}"
    new_link = Link(
        original_url=original_url,
        short_name=short_name,
        short_url=short_url
    )
    session.add(new_link)
    session.commit()
    session.refresh(new_link)
    return new_link

@app.get("/api/links/{link_id}")
def get_link(link_id: int, session: Session = Depends(get_session)):
    link = session.get(Link, link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    return link

@app.put("/api/links/{link_id}")
def update_link(link_id: int, link_data: dict, session: Session = Depends(get_session)):
    link = session.get(Link, link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    original_url = link_data.get("original_url")
    short_name = link_data.get("short_name")

    if original_url:
        link.original_url = original_url
    if short_name and short_name != link.short_name:
        existing = session.exec(select(Link).where(Link.short_name == short_name)).first()
        if existing:
            raise HTTPException(status_code=409, detail="short_name already exists")
        link.short_name = short_name
        link.short_url = f"{BASE_URL}/r/{short_name}"

    session.add(link)
    session.commit()
    session.refresh(link)
    return link

@app.delete("/api/links/{link_id}", status_code=204)
def delete_link(link_id: int, session: Session = Depends(get_session)):
    link = session.get(Link, link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    session.delete(link)
    session.commit()
    return None

@app.get("/r/{short_name}")
def redirect_to_original(short_name: str, session: Session = Depends(get_session)):
    link = session.exec(select(Link).where(Link.short_name == short_name)).first()
    if not link:
        raise HTTPException(status_code=404, detail="Short name not found")
    return RedirectResponse(url=link.original_url, status_code=302)
