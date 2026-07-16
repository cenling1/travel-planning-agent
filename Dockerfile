FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY aggentic_RAG/requirements.txt aggentic_RAG/setup.py /app/aggentic_RAG/
COPY aggentic_RAG/travel_agent /app/aggentic_RAG/travel_agent
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -e /app/aggentic_RAG

COPY . /app

EXPOSE 8000 8501
