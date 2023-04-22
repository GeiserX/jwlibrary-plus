FROM python:3.11-slim-buster

WORKDIR /app
RUN mkdir userBackups

COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

COPY . /app


CMD ["python", "src/bot.py"]