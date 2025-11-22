from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
hashed_password = pwd_context.hash("teacher123")

print(hashed_password)
# Copy the output. It will look something like:
# $2b$12$EixZaYVK1fsnwPKKFFBgce................