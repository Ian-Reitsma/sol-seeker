FROM python:3.11.6-slim@sha256:38a28170d13a276d42b7dd55cae54440b581d773549d361d19089ec47d4791c5
WORKDIR /app
COPY requirements.txt constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt
COPY . .
ARG COMMIT_SHA
ARG SCHEMA_HASH
RUN echo "$COMMIT_SHA" > version.txt && echo "$SCHEMA_HASH" > schema.txt
CMD ["python", "-m", "src.server"]
