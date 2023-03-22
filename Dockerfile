FROM python:3.9
COPY requirements.txt requirements.txt
COPY WebServer /WebServer
COPY SMB /SMB
COPY main.py main.py
RUN pip3 install -r requirements.txt
ENTRYPOINT ["python3", "main.py"]