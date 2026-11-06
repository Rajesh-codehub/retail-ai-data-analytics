from sqlalchemy import text

def test_database_connection(db):
    """Test that the database connection is successful."""
    result = db.execute(text("SELECT 1")).scalar()
    assert result == 1