FROM python:3.11-slim

WORKDIR /actor

RUN pip install --no-cache-dir google-adk uvicorn fastapi

COPY app/ /actor/app/
COPY server.py /actor/server.py

EXPOSE 8080

CMD ["python3", "/actor/server.py"]
