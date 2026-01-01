#!/bin/bash
mkdir -p certs
openssl req -x509 -newkey rsa:4096 -keyout certs/key.pem -out certs/cert.pem -days 365 -nodes -subj "/C=CN/ST=Beijing/L=Beijing/O=VoiceAssistant/OU=Dev/CN=localhost"
echo "Certificates generated in certs/"
