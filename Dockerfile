# Step 1: Use the official Python 3.12 base image
FROM python:3.12-slim

# Step 2: Set the working directory in the container
WORKDIR /app

# Step 3: Install system dependencies for wheel building (required by kiwipiepy and others)
# RUN apt-get update && apt-get install -y \
#     cmake \
#     build-essential \
#     libffi-dev \
#     libssl-dev \
#     python3-dev \
#     && apt-get clean

# Step 4: Upgrade pip and install numpy (to ensure compatibility for other dependencies)
# RUN pip install --upgrade pip setuptools wheel \
#     && pip install numpy

# # Step 5: Separate `kiwipiepy` installation for easier debugging
# RUN pip install kiwipiepy

# Step 6: Install remaining Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Step 7: Copy application files into the container
COPY . /app

# Step 8: Expose the port your application will run on (Streamlit example: 8501)
EXPOSE 8501

# Step 9: Specify the command to run the applicati
CMD ["streamlit", "run", "app_KOR.py"]