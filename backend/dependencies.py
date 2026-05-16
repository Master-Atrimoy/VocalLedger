from fastapi import Request
from sqlalchemy.orm import Session


def get_db(request: Request):
    session: Session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_graph(request: Request):
    return request.app.state.graph


def get_llm(request: Request):
    return request.app.state.llm


def get_stt(request: Request):
    return request.app.state.stt
