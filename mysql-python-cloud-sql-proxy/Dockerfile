FROM python:alpine

RUN apk add --update mariadb-dev libc-dev gcc

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app
COPY . /usr/src/app

RUN pip install -r requirements.txt

EXPOSE 5000

CMD [ "python","application.py"]
