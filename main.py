import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
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


@app.get("/ping", response_class=PlainTextResponse)
async def ping():
    return "pong"


def get_session():
    with Session(engine) as session:
        yield session


@app.get("/api/links")
def get_all_links(session: Session = Depends(get_session)):
    links = session.exec(select(Link)).all()
    return links


@app.post("/api/links", status_code=201)
def create_link(link_data: dict, session: Session = Depends(get_session)):

    original_url = link_data.get("original_url")
    short_name = link_data.get("short_name")
    if not original_url or not short_name:
        raise HTTPException(
            status_code=400, detail="original_url and short_name are required"
        )

    existing = session.exec(select(Link).where(Link.short_name == short_name)).first()
    if existing:
        raise HTTPException(status_code=409, detail="short_name already exists")

    short_url = f"{BASE_URL}/r/{short_name}"
    new_link = Link(
        original_url=original_url, short_name=short_name, short_url=short_url
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
    if short_name:
        if short_name != link.short_name:
            existing = session.exec(
                select(Link).where(Link.short_name == short_name)
            ).first()
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
    return
