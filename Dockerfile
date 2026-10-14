FROM python:3.11-slim
WORKDIR /workspace
COPY requirements.txt /opt/requirements.txt
RUN pip install --no-cache-dir -r /opt/requirements.txt
COPY research /workspace/research
COPY candidates /workspace/candidates
COPY scripts /workspace/scripts
RUN python scripts/test_requests.py && python scripts/test_king_optional.py
ENTRYPOINT ["python", "scripts/run_search.py"]
