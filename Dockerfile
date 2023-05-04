FROM python:3.9
WORKDIR /app/
COPY main.py requirements.txt ./
COPY WebServer ./WebServer
COPY SMB ./SMB
RUN pip install -r requirements.txt
ENTRYPOINT ["python3", "-u", "./main.py"]