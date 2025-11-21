#!/bin/bash
echo "🔒 Cleaning up plaintext secrets..."
rm -f surfsense_backend/secrets.yaml surfsense_backend/.env surfsense_backend/.env.backup.*
echo "✅ Done!"
