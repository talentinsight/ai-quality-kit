"""Tests for SQL normalization and comparison utilities."""

import unittest
from apps.utils.sql_normalize import canonicalize_sql, split_where_and_predicates, compare_sql


class TestSQLNormalize(unittest.TestCase):
    """Test SQL normalization functionality."""
    
    def test_canonicalize_sql_basic(self):
        """Test basic SQL canonicalization."""
        sql = "select name, age from users where city='Boston';"
        expected = "SELECT name, age FROM users WHERE city = 'Boston'"
        result = canonicalize_sql(sql)
        self.assertEqual(result, expected)
    
    def test_canonicalize_sql_whitespace(self):
        """Test whitespace normalization."""
        sql = "SELECT   name,age\n  FROM\tusers\r\nWHERE  city='Boston'"
        expected = "SELECT name, age FROM users WHERE city = 'Boston'"
        result = canonicalize_sql(sql)
        self.assertEqual(result, expected)
    
    def test_canonicalize_sql_comments(self):
        """Test comment removal."""
        sql = "SELECT name -- get name\nFROM users /* table comment */ WHERE city='Boston'"
        expected = "SELECT name FROM users WHERE city = 'Boston'"
        result = canonicalize_sql(sql)
        self.assertEqual(result, expected)
    
    def test_canonicalize_sql_keywords(self):
        """Test keyword uppercasing."""
        sql = "select distinct name from users left join orders on users.id = orders.user_id"
        expected = "SELECT DISTINCT name FROM users LEFT JOIN orders ON users.id = orders.user_id"
        result = canonicalize_sql(sql)
        self.assertEqual(result, expected)
    
    def test_canonicalize_sql_parentheses(self):
        """Test parentheses simplification."""
        sql = "(SELECT name FROM users WHERE age > 25)"
        expected = "SELECT name FROM users WHERE age > 25"
        result = canonicalize_sql(sql)
        self.assertEqual(result, expected)
    
    def test_split_where_and_predicates_simple(self):
        """Test splitting WHERE predicates with AND."""
        sql = "SELECT * FROM users WHERE city = 'Boston' AND age > 25"
        predicates = split_where_and_predicates(sql)
        expected = ["age > 25", "city = 'Boston'"]  # Sorted
        self.assertEqual(predicates, expected)
    
    def test_split_where_and_predicates_with_or(self):
        """Test that OR predicates return empty list."""
        sql = "SELECT * FROM users WHERE city = 'Boston' OR age > 25"
        predicates = split_where_and_predicates(sql)
        self.assertEqual(predicates, [])
    
    def test_split_where_and_predicates_no_where(self):
        """Test query without WHERE clause."""
        sql = "SELECT * FROM users"
        predicates = split_where_and_predicates(sql)
        self.assertEqual(predicates, [])
    
    def test_compare_sql_canonical_equal(self):
        """Test SQL comparison with canonical equality."""
        gold = "SELECT name, age FROM users WHERE city='Boston' AND age=30;"
        pred = "select name, age from users where age=30 and city = 'Boston'"
        
        result = compare_sql(gold, pred)
        
        # Should be equal either canonically or via WHERE-AND set equality
        self.assertTrue(result["canonical_equal"] or result["where_and_set_equal"])
        self.assertIn("GOLD:", result["normalized_sql_diff_preview"])
        self.assertIn("PRED:", result["normalized_sql_diff_preview"])
    
    def test_compare_sql_different_predicates(self):
        """Test SQL comparison with different predicates."""
        gold = "SELECT name FROM users WHERE city='Boston' AND age=30"
        pred = "SELECT name FROM users WHERE city='New York' AND age=25"
        
        result = compare_sql(gold, pred)
        
        self.assertFalse(result["canonical_equal"])
        self.assertFalse(result["where_and_set_equal"])
    
    def test_compare_sql_same_predicates_different_order(self):
        """Test SQL comparison with same predicates in different order."""
        gold = "SELECT name FROM users WHERE city='Boston' AND age=30"
        pred = "SELECT name FROM users WHERE age=30 AND city='Boston'"
        
        result = compare_sql(gold, pred)
        
        # Should be equal via WHERE-AND set equality even if not canonically equal
        self.assertTrue(result["where_and_set_equal"])
    
    def test_compare_sql_complex_query(self):
        """Test SQL comparison with complex query."""
        gold = "SELECT u.name, COUNT(o.id) FROM users u LEFT JOIN orders o ON u.id = o.user_id WHERE u.active = 1 GROUP BY u.name"
        pred = "SELECT u.name, count(o.id) from users u left join orders o on u.id = o.user_id where u.active = 1 group by u.name"
        
        result = compare_sql(gold, pred)
        
        self.assertTrue(result["canonical_equal"])
    
    def test_compare_sql_empty_queries(self):
        """Test SQL comparison with empty queries."""
        result = compare_sql("", "")
        self.assertTrue(result["canonical_equal"])
        
        result = compare_sql("SELECT 1", "")
        self.assertFalse(result["canonical_equal"])


if __name__ == '__main__':
    unittest.main()
