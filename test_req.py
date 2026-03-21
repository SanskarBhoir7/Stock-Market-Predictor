import urllib.request
import json

req = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/auth/register",
    data=json.dumps({
        "email": "test3@example.com",
        "username": "testuser3",
        "password": "Test@1234"
    }).encode('utf-8'),
    headers={'Content-Type': 'application/json'},
    method='POST'
)

try:
    with urllib.request.urlopen(req) as response:
        print("Success:", response.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code, e.read().decode('utf-8'))
except Exception as e:
    print("Connection error:", e)
