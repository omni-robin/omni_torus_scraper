FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y wget nano

# Upgrade pip and build tools
RUN pip install --upgrade pip setuptools wheel

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]