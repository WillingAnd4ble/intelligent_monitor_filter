import urllib.request
import json
req = urllib.request.Request("http://127.0.0.1:8000/auth/register", data=json.dumps({"email":"test20@test.com","password":"test"}).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
try:
    with urllib.request.urlopen(req) as f:
        print(f.status, f.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print("HTTPError:", e.code, e.read().decode('utf-8'))
except Exception as e:
    print("ERROR:", e)
