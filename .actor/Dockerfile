# Build context is the repo root (where .actor/ lives). We install the
# radar library from the local source — no GitHub clone at build time,
# so no rate limits.
FROM apify/actor-python:3.11

COPY . ./
RUN pip install --no-cache-dir -e .

CMD ["python", "-m", "actor"]
