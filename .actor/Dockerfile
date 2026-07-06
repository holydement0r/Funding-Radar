# Build context is the repo root (where .actor/ lives).
# We do NOT pip-install the local project — that build step was the only
# thing failing. Instead we install just the third-party runtime deps and
# run the actor straight from the copied source: both `radar/` and `actor/`
# sit in the workdir and import directly. The apify SDK ships in the base image.
FROM apify/actor-python:3.11

RUN pip install --no-cache-dir httpx jinja2

COPY . ./

CMD ["python", "-m", "actor"]
