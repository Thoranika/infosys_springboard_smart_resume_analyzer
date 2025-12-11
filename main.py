from utils.database import init_db, create_user, get_user_by_email

def main():
    # Create tables if they do not exist
    init_db()
    print("Database initialized ✅")

    # Example: create a test user (only first time)
    try:
        user_id = create_user(
            name="Test User",
            email="test@example.com",
            password_hash="dummy_hash",
        )
        print("Created user with id:", user_id)
    except ValueError as e:
        # If user already exists or email invalid
        print("Could not create user:", e)

    # Example: read user by email
    user = get_user_by_email("test@example.com")
    print("User from DB:", user)

if __name__ == "__main__":
    main()

