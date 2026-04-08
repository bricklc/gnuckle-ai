import unittest

from app import greet


class GreetingTests(unittest.TestCase):
    def test_greet_adds_comma_and_exclamation(self):
        self.assertEqual(greet("ape"), "Hello, ape!")


if __name__ == "__main__":
    unittest.main()
