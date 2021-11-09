FROM python:3.9.7-alpine

WORKDIR /app
COPY tg_downloader.py /app/tg_downloader.py
RUN apk update && apk upgrade && apk add build-base && pip install telethon cryptg
RUN chmod +x tg_downloader.py

ENTRYPOINT ["python"]
CMD ["/app/tg_downloader.py"]
