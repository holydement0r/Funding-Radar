# Build context is the repo root (where .actor/ lives). We install the
# radar library from the local source — no GitHub clone at build time,
# so no rate limits.
FROM apify/actor-python:3.11

COPY . ./
# Non-editable install: builds a wheel and installs radar into site-packages.
# Editable (-e) is fragile in containers; the actor package runs from the
# copied source via `python -m actor`.
RUN pip install --no-cache-dir .

CMD ["python", "-m", "actor"]
