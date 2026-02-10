#!/bin/bash

# The parent directory containing subfolders
PARENT_DIR="src/lambda_layers"

# Change to the parent directory
cd "$PARENT_DIR"

# Check if changing directory was successful
if [ $? -ne 0 ]; then
  echo "Failed to change directory to $PARENT_DIR"
  exit 1
fi

# Loop through each subfolder and run a command
for SUBDIR in */ ; do
  if [ -d "$SUBDIR" ]; then
    echo "Entering directory: $SUBDIR"

    # Check if subdirectory name contains "agentcore"
    if [[ "$SUBDIR" == *"agentcore"* ]]; then
      echo "⏭️  Skipping directory: $SUBDIR (does not contain 'agentcore')"
      SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
      continue
    else
      echo "✅ Found agentcore directory: $SUBDIR - Processing..."
      PROCESSED_COUNT=$((PROCESSED_COUNT + 1))
      cd "$SUBDIR"
    fi

    # Check if requirements.txt exists
    if [ -f "requirements.txt" ]; then
      echo "Found requirements.txt in $(pwd)"
      
      # Check if layer.zip exists and if requirements.txt is newer than layer.zip
      if [ ! -f "layer.zip" ] || [ "requirements.txt" -nt "layer.zip" ]; then
        echo "Requirements.txt is new or modified. Building layer..."
        
        # Remove existing layer.zip if it exists
        if [ -f "layer.zip" ]; then
          rm layer.zip
        fi
        
        # Install dependencies and create layer
        pip3 install -r requirements.txt --platform manylinux2014_x86_64 --only-binary=:all: --implementation cp --target=python/ --upgrade --python-version 3.12
        rm -rf python/boto*
        rm -rf python/urllib*
        rm -rf python/s3transfer*
        find . -type d -name 'tests' -exec rm -rf {} +
        find . -type d -name '__pycache__' -exec rm -rf {} +
        zip -r layer.zip python/
        rm -rf python
        echo "Layer created successfully."
      else
        echo "Layer.zip is up to date. Skipping rebuild."
      fi
    else
      echo "No requirements.txt found in $(pwd)"
      if [ -d "python" ] && [ ! -f "layer.zip" ]; then
        echo "Python directory exists but no layer.zip. Creating layer..."
        zip -r layer.zip python/
        echo "Layer created successfully."
      fi
    fi

    # Always check if you need to return to the parent directory
    cd ..
  fi
done
