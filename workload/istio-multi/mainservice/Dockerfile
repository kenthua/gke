FROM python:3.11-slim AS build-env
ADD . /app
WORKDIR /app
RUN pip install -r requirements.txt

FROM gcr.io/distroless/python3
COPY --from=build-env /app /app
COPY --from=build-env /usr/local/lib/python3.11/site-packages /home/.local/lib/python3.11/site-packages
WORKDIR /app
CMD ["main.py"]

