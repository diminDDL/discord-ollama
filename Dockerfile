# Based on https://github.com/ThatRedKite/thatkitebot/
FROM python:3.12-bullseye

WORKDIR /app/

COPY ./requirements.txt /tmp/requirements.txt
COPY ./ollamads /app/ollamads

WORKDIR /tmp/

RUN apt-get update && apt-get upgrade -y

RUN apt-get install -y git

RUN pip3 install --upgrade pip

RUN pip3 install -r requirements.txt

RUN pip3 install -U "py-cord[speed]"

RUN pip3 install "redis[hiredis]"

WORKDIR /app/

