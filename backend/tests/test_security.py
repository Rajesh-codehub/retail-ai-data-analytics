from app.core.security import hash_password, verify_password


def test_password_hashing():
    password = "MyPassword123"

    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)


def test_incorrect_password():
    hashed = hash_password("MyPassword123")

    assert not verify_password("WrongPassword123", hashed)


def test_same_password_generates_different_hashes():
    password = "MyPassword123"

    hash1 = hash_password(password)
    hash2 = hash_password(password)

    assert hash1 != hash2
    assert verify_password(password, hash1)
    assert verify_password(password, hash2)