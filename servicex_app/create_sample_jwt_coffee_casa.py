import jwt

sha_256_secret = '1e57a452a094728c291bc42bf2bc7eb8d9fd8844d1369da2bf728588b46c4e75'

payload_data = {
    "sub": "prajwal",
    "name": "Jane Doe",
    "email": "prajwal@example.com",
    "institution": "UChicago",
    "admin": False,
    "id": 2,
    "experiment": 'ATLAS'
}

new_token = jwt.encode(
    payload=payload_data,
    key=sha_256_secret,
    algorithm='HS256'
)

print(new_token)

jwt.get_unverified_header(new_token)

decoded_val = jwt.decode(jwt=new_token, key=sha_256_secret, algorithms=['HS256'])

print(decoded_val)
