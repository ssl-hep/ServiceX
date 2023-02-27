import jwt
from cryptography.hazmat.primitives import serialization

private_key = open('jwt_rsa', 'r').read()

key_val = serialization.load_ssh_private_key(private_key.encode(), password=b'foo')

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
    key=key_val,
    algorithm='RS256'
)

print(new_token)

jwt.get_unverified_header(new_token)

public_key = open('jwt_rsa.pub', 'r').read()
key_decode = serialization.load_ssh_public_key(public_key.encode())

decoded_val = jwt.decode(jwt=new_token, key=key_decode, algorithms=['RS256', ])

print(decoded_val)