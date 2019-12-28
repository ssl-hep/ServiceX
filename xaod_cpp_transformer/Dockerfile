# Build a docker image to run against ATLAS code that has been pre-built and is ready to go.

FROM atlas/analysisbase:21.2.102

WORKDIR /home/atlas
COPY requirements.txt .
RUN source /home/atlas/release_setup.sh; \
    pip install --user -r requirements.txt
RUN source /home/atlas/release_setup.sh; \
    pip install --user --index-url https://test.pypi.org/simple/ --no-deps servicex==0.2-b

# Turn this on so that stdout isn't buffered - otherwise logs in kubectl don't
# show up until much later!
ENV PYTHONUNBUFFERED=1

# Copy over the source
COPY xAOD_CPP_Transformer.py .

ENTRYPOINT [ "python", "xAOD_CPP_Transformer.py" ]
