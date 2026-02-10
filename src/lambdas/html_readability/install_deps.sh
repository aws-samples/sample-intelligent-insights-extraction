#!/bin/bash

# Script to install Node.js dependencies for the Lambda function
cd "$(dirname "$0")"
npm install
echo "Dependencies installed successfully"
