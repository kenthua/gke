FROM python:3-alpine

ADD app.py \
    requirements.txt /

RUN pip install -r requirements.txt

CMD ["python", "./app.py"]