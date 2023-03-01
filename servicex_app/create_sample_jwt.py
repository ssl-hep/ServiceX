import jwt
from cryptography.hazmat.primitives import serialization

private_key = open('jwt_rsa', 'r').read()

key_val = serialization.load_ssh_private_key(private_key.encode(), password=b'foo')

payload = {
  "sub": "bbockelm",
  "exp": 1685677084,
  "iat": 1509988190,
  "jti": "515c0084-cb1b-4a63-bce9-b9d6ace17ccb",
  "iss": "https://scitokens.org/cms",
  "scope": "read:/store write:/store/user/bbockelm",
  "name": "Jane Doe",
  "email": "prajwal@example.com",
  "nbf": 1509988190,
  "ver": "scitoken:2.0"
}

new_token = jwt.encode(
    payload=payload,
    key=key_val,
    algorithm='RS256'
)

print(new_token)

jwt.get_unverified_header(new_token)

public_key = open('jwt_rsa.pub', 'r').read()
key_decode = serialization.load_ssh_public_key(public_key.encode())

decoded_val = jwt.decode(jwt=new_token, key=key_decode, algorithms=['RS256', ])

print(decoded_val)
