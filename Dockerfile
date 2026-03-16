FROM python:3.12-alpine AS builder

RUN apk add --no-cache gcc musl-dev libffi-dev

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-alpine

RUN apk add --no-cache libffi

COPY --from=builder /install /usr/local
WORKDIR /app
COPY app/ app/

EXPOSE 8080

CMD ["python", "-m", "app.main"]
