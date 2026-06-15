from cryptography.fernet import Fernet
import os

cipher = Fernet(os.getenv("FERNET_KEY").encode())

def encrypt(data: str):
    return cipher.encrypt(data.encode()).decode()

def decrypt(data: str):
    return cipher.decrypt(data.encode()).decode()
