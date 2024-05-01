FROM python:3.12-slim-buster

WORKDIR /app
RUN apt-get update && apt-get install -y locales-all abiword build-essential xvfb
RUN mkdir userBackups

COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

COPY . /app

CMD ["python", "-u", "src/bot.py"]