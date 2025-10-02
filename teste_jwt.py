import jwt
import os
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET", "AmendoimTorradassoNaSenha")

token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MSwiZW1haWwiOiJyYWVsQGdtYWlsLmNvbSIsInBlcmZpbCI6ImNvbnN1bWlkb3IiLCJpYXQiOjE3NTk0MzI3NDEsImV4cCI6MTc1OTQzNjM0MX0.dMG-4cVF3ASyeQq4DcyC6aXdVhiRnA-2M3_Bfc5uO5g"

try:
    decoded = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    print("Token decodificado com sucesso!")
    print(decoded)
except jwt.ExpiredSignatureError:
    print("Token expirado.")
except jwt.InvalidTokenError:
    print("Token inválido.")
