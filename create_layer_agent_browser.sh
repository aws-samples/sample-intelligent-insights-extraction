#!/bin/bash

# The parent directory containing subfolders
PARENT_DIR="src/lambda_layers"

# Initialize counters
PROCESSED_COUNT=0
SKIPPED_COUNT=0

echo "🚀 Starting agentcore layer build process..."
echo "📁 Looking for directories containing 'agentcore' in: $PARENT_DIR"

# Change to the parent directory
cd "$PARENT_DIR"

# Check if changing directory was successful
if [ $? -ne 0 ]; then
  echo "❌ Failed to change directory to $PARENT_DIR"
  exit 1
fi

# Loop through each subfolder and run a command
for SUBDIR in */ ; do
  if [ -d "$SUBDIR" ]; then
    # Check if subdirectory name contains "agentcore"
    if [[ "$SUBDIR" == *"agentcore"* ]]; then
      echo "✅ Found agentcore directory: $SUBDIR - Processing..."
      PROCESSED_COUNT=$((PROCESSED_COUNT + 1))
      cd "$SUBDIR"
    else
      echo "⏭️  Skipping directory: $SUBDIR (does not contain 'agentcore')"
      SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
      continue
    fi

    # Check if requirements.txt exists
    if [ -f "requirements.txt" ]; then
      echo "📋 Found requirements.txt in $(pwd)"
      
      # Check if layer.zip exists and if requirements.txt is newer than layer.zip
      if [ ! -f "layer.zip" ] || [ "requirements.txt" -nt "layer.zip" ]; then
        echo "🔨 Requirements.txt is new or modified. Building layer..."
        
        # Remove existing layer.zip if it exists
        if [ -f "layer.zip" ]; then
          rm layer.zip
        fi
        
        # Install dependencies and create layer
        echo "📦 Installing dependencies..."
        pip3 install -r requirements.txt --platform manylinux2014_x86_64 --only-binary=:all: --implementation cp --target=python/ --upgrade --python-version 3.12
        
        echo "🧹 Cleaning up unnecessary packages..."
        rm -rf python/urllib*
        rm -rf python/s3transfer*
        find . -type d -name 'tests' -exec rm -rf {} +
        find . -type d -name '__pycache__' -exec rm -rf {} +
        
        echo "📦 Creating layer.zip..."
        zip -r layer.zip python/
        rm -rf python
        echo "✅ Layer created successfully for agentcore directory: $SUBDIR"
      else
        echo "⏭️  Layer.zip is up to date. Skipping rebuild."
      fi
    else
      echo "❌ No requirements.txt found in agentcore directory: $(pwd)"
      echo "⚠️  Agentcore directories must have requirements.txt to build layers"
      if [ -d "python" ] && [ ! -f "layer.zip" ]; then
        echo "🔧 Python directory exists but no layer.zip. Creating layer from existing python dir..."
        zip -r layer.zip python/
        echo "✅ Layer created successfully from existing python directory."
      fi
    fi

    # Always check if you need to return to the parent directory
    cd ..
  fi
done

echo ""
echo "📊 Build Summary:"
echo "   ✅ Processed agentcore directories: $PROCESSED_COUNT"
echo "   ⏭️  Skipped non-agentcore directories: $SKIPPED_COUNT"
echo "🎉 Agentcore layer build process completed!"
